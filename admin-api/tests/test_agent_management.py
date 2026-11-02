import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from admin_api import agent_management, enrollment, main
from admin_api.agent_management import (
    AgentManagementCallerNotAdmin,
    AgentManagementService,
    AgentNotFound,
    AgentRecord,
    AgentRoleChangeUnavailable,
)
from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.enrollment import (
    IdentityCompensationFailed,
    IdentityProviderUnavailable,
    KeycloakAdminClient,
)

ADMIN_SUBJECT = "00000000-0000-0000-0000-000000000004"
FIRST_AGENT_ID = UUID("00000000-0000-0000-0000-000000000010")
SECOND_AGENT_ID = UUID("00000000-0000-0000-0000-000000000020")


class FakeStore:
    def __init__(
        self,
        records: list[AgentRecord] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.list_request: tuple[object, ...] | None = None
        self.role_change: tuple[UUID, UUID, str, str] | None = None

    async def list_agents(
        self,
        caller_id: UUID,
        status: str | None,
        ministry_code: str | None,
        after_id: UUID | None,
        limit: int,
    ) -> list[AgentRecord]:
        self.list_request = (caller_id, status, ministry_code, after_id, limit)
        if self.error:
            raise self.error
        return self.records[:limit]

    async def get_agent(self, caller_id: UUID, agent_id: UUID) -> AgentRecord:
        if self.error:
            raise self.error
        for record in self.records:
            if record.id == agent_id:
                return record
        raise AgentNotFound

    async def change_agent_role(
        self,
        caller_id: UUID,
        agent_id: UUID,
        new_role: str,
        role_manager,
    ) -> AgentRecord:
        if self.error:
            raise self.error
        for index, item in enumerate(self.records):
            if item.id == agent_id:
                try:
                    await role_manager.change_role(
                        UUID("00000000-0000-0000-0000-000000000099"),
                        item.role,
                        new_role,
                    )
                except IdentityProviderUnavailable as error:
                    raise AgentRoleChangeUnavailable from error
                self.role_change = (caller_id, agent_id, item.role, new_role)
                self.records[index] = replace(item, role=new_role)
                return self.records[index]
        raise AgentNotFound


class FakeRoleManager:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[UUID, str, str]] = []

    async def change_role(self, keycloak_id: UUID, old_role: str, new_role: str) -> None:
        self.calls.append((keycloak_id, old_role, new_role))
        if self.error:
            raise self.error


def settings() -> Settings:
    return Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
    )


def record(agent_id: UUID = FIRST_AGENT_ID) -> AgentRecord:
    return AgentRecord(
        id=agent_id,
        identifiant="agent.demo1",
        matrix_id="@agent.demo1:oryma.local",
        nom_complet="Agent Démo 1",
        ministere_code="MIN-DEMO-A",
        fonction="Chargé d’études",
        role="agent",
        statut="actif",
        cree_le=datetime(2026, 11, 1, tzinfo=UTC),
        revoque_le=None,
    )


def run(awaitable):
    return asyncio.run(awaitable)


def test_list_agents_returns_page_and_cursor_with_filters() -> None:
    store = FakeStore([record(FIRST_AGENT_ID), record(SECOND_AGENT_ID)])
    service = AgentManagementService(settings(), store)

    result = run(
        service.list_agents(
            Principal(ADMIN_SUBJECT, frozenset({"admin"})),
            "actif",
            "MIN-DEMO-A",
            None,
            1,
        )
    )

    assert result["items"] == [record(FIRST_AGENT_ID).as_response()]
    assert result["next_cursor"] == service._encode_cursor(FIRST_AGENT_ID)
    assert store.list_request == (
        UUID(ADMIN_SUBJECT),
        "actif",
        "MIN-DEMO-A",
        None,
        2,
    )


def test_list_agents_rejects_malformed_cursor_without_querying_store() -> None:
    store = FakeStore()
    service = AgentManagementService(settings(), store)

    with pytest.raises(agent_management.ApiError) as raised:
        run(
            service.list_agents(
                Principal(ADMIN_SUBJECT, frozenset({"admin"})),
                None,
                None,
                "not-a-cursor",
                50,
            )
        )

    assert raised.value.status_code == 422
    assert raised.value.code == "ERR-023"
    assert store.list_request is None


def test_agent_detail_returns_not_found_error() -> None:
    service = AgentManagementService(settings(), FakeStore())

    with pytest.raises(agent_management.ApiError) as raised:
        run(
            service.get_agent(
                Principal(ADMIN_SUBJECT, frozenset({"admin"})),
                FIRST_AGENT_ID,
            )
        )

    assert raised.value.status_code == 404
    assert raised.value.code == "ERR-031"


def test_agent_management_rejects_admin_not_active_in_registry() -> None:
    service = AgentManagementService(
        settings(),
        FakeStore(error=AgentManagementCallerNotAdmin()),
    )

    with pytest.raises(agent_management.ApiError) as raised:
        run(
            service.list_agents(
                Principal(ADMIN_SUBJECT, frozenset({"admin"})),
                None,
                None,
                None,
                50,
            )
        )

    assert raised.value.status_code == 403
    assert raised.value.code == "ERR-014"


def test_change_role_updates_identity_and_returns_agent() -> None:
    store = FakeStore([record()])
    role_manager = FakeRoleManager()
    service = AgentManagementService(settings(), store, role_manager)

    result = run(
        service.change_role(
            Principal(ADMIN_SUBJECT, frozenset({"admin"})),
            FIRST_AGENT_ID,
            "admin",
        )
    )

    assert result["role"] == "admin"
    assert store.role_change == (
        UUID(ADMIN_SUBJECT),
        FIRST_AGENT_ID,
        "agent",
        "admin",
    )
    assert role_manager.calls == [(UUID("00000000-0000-0000-0000-000000000099"), "agent", "admin")]


def test_change_role_fails_explicitly_when_identity_provider_is_unavailable() -> None:
    service = AgentManagementService(
        settings(),
        FakeStore([record()]),
        FakeRoleManager(IdentityProviderUnavailable()),
    )

    with pytest.raises(agent_management.ApiError) as raised:
        run(
            service.change_role(
                Principal(ADMIN_SUBJECT, frozenset({"admin"})),
                FIRST_AGENT_ID,
                "admin",
            )
        )

    assert raised.value.status_code == 503
    assert raised.value.code == "ERR-500"


def test_keycloak_role_change_adds_new_role_then_removes_old(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "service-token"})
        if request.method == "GET" and "/roles/" in request.url.path:
            role_name = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": f"id-{role_name}", "name": role_name})
        if request.method in {"POST", "DELETE"} and request.url.path.endswith(
            "/role-mappings/realm"
        ):
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    identity_settings = Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
        oidc_issuer="https://oryma.local/auth/realms/oryma",
        oidc_jwks_url="http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs",
        keycloak_admin_client_secret="test-only",
    )
    client = KeycloakAdminClient(identity_settings)

    run(
        client.change_role(
            UUID("00000000-0000-0000-0000-000000000099"),
            "agent",
            "admin",
        )
    )

    mappings = [
        request for request in requests if request.url.path.endswith("/role-mappings/realm")
    ]
    assert [request.method for request in mappings] == ["POST", "DELETE"]
    assert b"id-admin" in mappings[0].content
    assert b"id-agent" in mappings[1].content


def test_keycloak_role_change_restores_old_role_when_removal_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    removal_attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal removal_attempts
        requests.append(request)
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "service-token"})
        if request.method == "GET" and "/roles/" in request.url.path:
            role_name = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": f"id-{role_name}", "name": role_name})
        if request.method == "POST" and request.url.path.endswith("/role-mappings/realm"):
            return httpx.Response(204)
        if request.method == "DELETE" and request.url.path.endswith("/role-mappings/realm"):
            removal_attempts += 1
            return httpx.Response(500 if removal_attempts == 1 else 204)
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    identity_settings = Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
        oidc_issuer="https://oryma.local/auth/realms/oryma",
        oidc_jwks_url="http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs",
        keycloak_admin_client_secret="test-only",
    )
    client = KeycloakAdminClient(identity_settings)

    with pytest.raises(IdentityProviderUnavailable):
        run(
            client.change_role(
                UUID("00000000-0000-0000-0000-000000000099"),
                "agent",
                "admin",
            )
        )

    mappings = [
        request for request in requests if request.url.path.endswith("/role-mappings/realm")
    ]
    assert [request.method for request in mappings] == ["POST", "DELETE", "POST", "DELETE"]
    assert b"id-agent" in mappings[2].content
    assert b"id-admin" in mappings[3].content


def test_keycloak_role_change_reports_failed_compensation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    removal_attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal removal_attempts
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "service-token"})
        if request.method == "GET" and "/roles/" in request.url.path:
            role_name = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": f"id-{role_name}", "name": role_name})
        if request.method == "POST" and request.url.path.endswith("/role-mappings/realm"):
            return httpx.Response(500 if removal_attempts else 204)
        if request.method == "DELETE" and request.url.path.endswith("/role-mappings/realm"):
            removal_attempts += 1
            return httpx.Response(500)
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    identity_settings = Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
        oidc_issuer="https://oryma.local/auth/realms/oryma",
        oidc_jwks_url="http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs",
        keycloak_admin_client_secret="test-only",
    )
    client = KeycloakAdminClient(identity_settings)

    with pytest.raises(IdentityCompensationFailed):
        run(
            client.change_role(
                UUID("00000000-0000-0000-0000-000000000099"),
                "agent",
                "admin",
            )
        )


def test_http_agent_list_uses_admin_dependency_and_contract_envelope() -> None:
    app: FastAPI = main.create_app(settings())
    store = FakeStore([record()])
    app.state.agent_management_service = AgentManagementService(settings(), store)
    app.dependency_overrides[require_admin] = lambda: Principal(
        ADMIN_SUBJECT,
        frozenset({"admin"}),
    )

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/agents?statut=actif&page_size=1")

    response = run(send())

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["id"] == str(FIRST_AGENT_ID)
    assert response.json()["data"]["next_cursor"] is None
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_http_agent_role_change_uses_admin_dependency_and_contract_envelope() -> None:
    app: FastAPI = main.create_app(settings())
    store = FakeStore([record()])
    app.state.agent_management_service = AgentManagementService(
        settings(),
        store,
        FakeRoleManager(),
    )
    app.dependency_overrides[require_admin] = lambda: Principal(
        ADMIN_SUBJECT,
        frozenset({"admin"}),
    )

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.patch(
                f"/api/v1/agents/{FIRST_AGENT_ID}/role",
                json={"role": "admin"},
            )

    response = run(send())

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
