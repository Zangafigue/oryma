import asyncio
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from admin_api.config import Settings
from admin_api.errors import ApiError
from admin_api.health import check_database, check_http_endpoint


async def render_api_error(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
            "request_id": request.state.request_id,
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Oryma Admin API", version="0.1.0")
    app.state.settings = settings or Settings.from_environment()
    app.add_exception_handler(ApiError, render_api_error)

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
