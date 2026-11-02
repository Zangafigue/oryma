import asyncio
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from admin_api import audit, main
from admin_api.audit import AuditEvent, AuditService
from admin_api.auth import Principal, require_admin
from admin_api.config import Settings

ADMIN_SUBJECT = "00000000-0000-0000-0000-000000000004"
FIRST_EVENT = AuditEvent(
    id=8,
    action="REVOCATION",
    actor_id=UUID(ADMIN_SUBJECT),
    target_id=UUID("00000000-0000-0000-0000-000000000010"),
    details={"etapes": [1, 2, 3, 4, 5, 6]},
    timestamp=datetime(2026, 11, 2, tzinfo=UTC),
)
SECOND_EVENT = AuditEvent(
    id=7,
    action="REVOCATION",
    actor_id=UUID(ADMIN_SUBJECT),
    target_id=UUID("00000000-0000-0000-0000-000000000011"),
    details={"role": "agent"},
    timestamp=datetime(2026, 11, 1, tzinfo=UTC),
)


class FakeStore:
    def __init__(self, events: list[AuditEvent] | None = None) -> None:
        self.events = events or []
        self.list_request: tuple[object, ...] | None = None

    async def list_events(
        self,
        actor_id: UUID,
        action: str | None,
        actor_filter: UUID | None,
        since: datetime | None,
        until: datetime | None,
        after_id: int | None,
        limit: int,
    ) -> list[AuditEvent]:
        self.list_request = (actor_id, action, actor_filter, since, until, after_id, limit)
        filtered = [
            event
            for event in self.events
            if (action is None or event.action == action)
            and (actor_filter is None or event.actor_id == actor_filter)
            and (since is None or event.timestamp >= since)
            and (until is None or event.timestamp <= until)
            and (after_id is None or event.id < after_id)
        ]
        return filtered[:limit]


def settings() -> Settings:
    return Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
    )


def run(awaitable):
    return asyncio.run(awaitable)


def test_list_audit_events_returns_cursor_and_filters() -> None:
    store = FakeStore([FIRST_EVENT, SECOND_EVENT])
    service = AuditService(settings(), store)

    result = run(
        service.list_events(
            Principal(ADMIN_SUBJECT, frozenset({"admin"})),
            "REVOCATION",
            UUID(ADMIN_SUBJECT),
            datetime(2026, 11, 1, tzinfo=UTC),
            datetime(2026, 11, 3, tzinfo=UTC),
            None,
            1,
        )
    )

    assert result["items"] == [FIRST_EVENT.as_response()]
    assert result["next_cursor"] == service._encode_cursor(FIRST_EVENT.id)
    assert store.list_request == (
        UUID(ADMIN_SUBJECT),
        "REVOCATION",
        UUID(ADMIN_SUBJECT),
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 11, 3, tzinfo=UTC),
        None,
        2,
    )


def test_invalid_audit_cursor_is_rejected_before_store_access() -> None:
    store = FakeStore([FIRST_EVENT])
    service = AuditService(settings(), store)

    with pytest.raises(audit.ApiError) as raised:
        run(
            service.list_events(
                Principal(ADMIN_SUBJECT, frozenset({"admin"})),
                None,
                None,
                None,
                None,
                "invalid",
                50,
            )
        )

    assert raised.value.status_code == 422
    assert raised.value.code == "ERR-023"
    assert store.list_request is None


def test_invalid_audit_date_range_is_rejected() -> None:
    store = FakeStore([FIRST_EVENT])
    service = AuditService(settings(), store)

    with pytest.raises(audit.ApiError) as raised:
        run(
            service.list_events(
                Principal(ADMIN_SUBJECT, frozenset({"admin"})),
                None,
                None,
                datetime(2026, 11, 3, tzinfo=UTC),
                datetime(2026, 11, 1, tzinfo=UTC),
                None,
                50,
            )
        )

    assert raised.value.status_code == 422
    assert store.list_request is None


def test_audit_route_returns_filtered_events() -> None:
    app = main.create_app(settings())
    store = FakeStore([FIRST_EVENT, SECOND_EVENT])
    app.state.audit_service = AuditService(settings(), store)
    app.dependency_overrides[require_admin] = lambda: Principal(
        ADMIN_SUBJECT,
        frozenset({"admin"}),
    )

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/audit?action=REVOCATION&page_size=1")

    response = run(send())

    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["id"] == FIRST_EVENT.id
    assert item["action"] == FIRST_EVENT.action
    assert response.json()["data"]["next_cursor"] is not None
