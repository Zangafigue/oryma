import asyncio

import httpx
import pytest

from admin_api import main
from admin_api.config import Settings


def settings(environment: str, enabled: bool) -> Settings:
    return Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
        environment=environment,
        enable_local_oidc_harness=enabled,
    )


@pytest.mark.parametrize(
    ("environment", "enabled", "expected_status"),
    [
        ("development", True, 200),
        ("production", True, 404),
        ("development", False, 404),
    ],
)
def test_local_oidc_harness_is_only_served_when_explicitly_enabled(
    environment: str,
    enabled: bool,
    expected_status: int,
) -> None:
    app = main.create_app(settings(environment, enabled))

    async def send() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/admin/"), await client.get("/admin/app.js")

    index_response, script_response = asyncio.run(send())

    assert index_response.status_code == expected_status
    assert script_response.status_code == expected_status
    if expected_status == 200:
        assert "Test local OIDC, agents, révocation et salles" in index_response.text
        assert "Tester POST /api/v1/agents/{id}/revoke" in index_response.text
        assert 'code_challenge_method: "S256"' in script_response.text
        assert "GET /api/v1/levels" in index_response.text
        assert "POST /api/v1/rooms" in index_response.text
        assert "GET /api/v1/rooms" in index_response.text
        assert '"/api/v1/levels"' in script_response.text
        assert '"/api/v1/rooms"' in script_response.text
        assert "duree_vie_secondes" in script_response.text
