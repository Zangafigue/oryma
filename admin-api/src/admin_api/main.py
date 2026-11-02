import asyncio
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from admin_api.agent_management import AgentManagementService
from admin_api.agent_management import router as agent_management_router
from admin_api.audit import AuditService
from admin_api.audit import router as audit_router
from admin_api.auth import JwksClient
from admin_api.config import Settings
from admin_api.enrollment import EnrollmentService
from admin_api.enrollment import router as enrollment_router
from admin_api.errors import ApiError
from admin_api.health import check_database, check_http_endpoint
from admin_api.revocation import RevocationService
from admin_api.revocation import router as revocation_router
from admin_api.rooms import RoomService
from admin_api.rooms import router as rooms_router


async def render_api_error(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        headers={"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
            "request_id": request.state.request_id,
        },
    )


async def render_validation_error(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    fields = [
        {
            "champ": ".".join(str(part) for part in item["loc"] if part != "body"),
            "erreur": item["type"],
        }
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "ERR-023",
                "message": "Les données envoyées sont invalides.",
                "details": {"champs": fields},
            },
            "request_id": request.state.request_id,
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Oryma Admin API", version="0.1.0")
    app.state.settings = settings or Settings.from_environment()
    app.state.jwks_client = JwksClient(app.state.settings.oidc_jwks_url or "")
    app.state.audit_service = AuditService(app.state.settings)
    app.state.enrollment_service = EnrollmentService(app.state.settings)
    app.state.agent_management_service = AgentManagementService(app.state.settings)
    app.state.revocation_service = RevocationService(app.state.settings)
    app.state.room_service = RoomService(app.state.settings)
    app.add_exception_handler(ApiError, render_api_error)
    app.add_exception_handler(RequestValidationError, render_validation_error)
    app.include_router(enrollment_router)
    app.include_router(agent_management_router)
    app.include_router(audit_router)
    app.include_router(revocation_router)
    app.include_router(rooms_router)
    if (
        app.state.settings.environment == "development"
        and app.state.settings.enable_local_oidc_harness
    ):
        app.mount(
            "/admin",
            StaticFiles(
                directory=str(Path(__file__).parent / "dev_harness"),
                html=True,
            ),
            name="local-oidc-harness",
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next) -> Response:
        supplied_id = request.headers.get("X-Request-ID")
        try:
            request_id = str(UUID(supplied_id)) if supplied_id else str(uuid4())
        except ValueError:
            request_id = str(uuid4())

        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health")
    async def health(request: Request, response: Response) -> dict[str, object]:
        settings: Settings = request.app.state.settings
        database_ok, keycloak_ok, synapse_ok = await asyncio.gather(
            check_database(settings.database_url),
            check_http_endpoint(settings.keycloak_healthcheck_url),
            check_http_endpoint(settings.synapse_healthcheck_url),
        )
        checks = {
            "database": "ok" if database_ok else "error",
            "keycloak": "ok" if keycloak_ok else "error",
            "synapse": "ok" if synapse_ok else "error",
        }
        is_healthy = all(check == "ok" for check in checks.values())
        response.status_code = 200 if is_healthy else 503
        return {"status": "ok" if is_healthy else "error", "checks": checks}

    return app


app = create_app()
