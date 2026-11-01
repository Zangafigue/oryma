import asyncio

import httpx
from fastapi import FastAPI

from admin_api import main
from admin_api.config import Settings


def get_health(app: FastAPI, headers: dict[str, str] | None = None) -> httpx.Response:
    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health", headers=headers)

    return asyncio.run(request_health())


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

    response = get_health(
        app,
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

    response = get_health(app, headers={"X-Request-ID": "invalid"})

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "checks": {"database": "error", "keycloak": "ok", "synapse": "ok"},
    }
    assert response.headers["X-Request-ID"] != "invalid"
