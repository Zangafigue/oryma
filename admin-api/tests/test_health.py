import asyncio

import httpx
from fastapi import FastAPI

from admin_api import main
from admin_api.config import Settings
from admin_api.errors import ApiError


def request_app(
    app: FastAPI,
    path: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers)

    return asyncio.run(send_request())


def test_health_reports_all_dependencies_and_request_id(monkeypatch) -> None:
    async def dependency_ok(_url: str | None) -> bool:
        return True

    monkeypatch.setattr(main, "check_database", dependency_ok)
    monkeypatch.setattr(main, "check_http_endpoint", dependency_ok)
    app = main.create_app(
        Settings(
            database_url="postgresql://test",
            keycloak_healthcheck_url="http://keycloak/health/ready",
            synapse_healthcheck_url="http://synapse/health",
        )
    )

    response = request_app(
        app,
        "/health",
        headers={"X-Request-ID": "b9c9b9e8-78da-44e1-a7ee-3f6861a6f60a"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "keycloak": "ok", "synapse": "ok"},
    }
    assert response.headers["X-Request-ID"] == "b9c9b9e8-78da-44e1-a7ee-3f6861a6f60a"


def test_health_fails_when_a_dependency_is_unavailable(monkeypatch) -> None:
    async def dependency_ok(_url: str | None) -> bool:
        return True

    async def database_unavailable(_url: str | None) -> bool:
        return False

    monkeypatch.setattr(main, "check_database", database_unavailable)
    monkeypatch.setattr(main, "check_http_endpoint", dependency_ok)
    app = main.create_app(
        Settings(
            database_url="postgresql://test",
            keycloak_healthcheck_url="http://keycloak/health/ready",
            synapse_healthcheck_url="http://synapse/health",
        )
    )

    response = request_app(app, "/health", headers={"X-Request-ID": "invalid"})

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "checks": {"database": "error", "keycloak": "ok", "synapse": "ok"},
    }
    assert response.headers["X-Request-ID"] != "invalid"


def test_api_error_uses_common_envelope_and_request_id() -> None:
    app = main.create_app(
        Settings(
            database_url=None,
            keycloak_healthcheck_url=None,
            synapse_healthcheck_url=None,
        )
    )

    @app.get("/test-forbidden")
    async def forbidden() -> None:
        raise ApiError(
            status_code=403,
            code="ERR-014",
            message="Rôle insuffisant pour cette opération.",
        )

    request_id = "7b1c2d34-0f1e-4a8b-9c3d-2e5f6a7b8c9d"
    response = request_app(
        app,
        "/test-forbidden",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "ERR-014",
            "message": "Rôle insuffisant pour cette opération.",
            "details": {},
        },
        "request_id": request_id,
    }
    assert response.headers["X-Request-ID"] == request_id
