import asyncio
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from admin_api import agent_management, main
from admin_api.agent_management import (
    AgentManagementCallerNotAdmin,
    AgentManagementService,
    AgentNotFound,
    AgentRecord,
)
from admin_api.auth import Principal, require_admin
from admin_api.config import Settings

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
