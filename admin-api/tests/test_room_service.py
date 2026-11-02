import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from admin_api import main, rooms
from admin_api.auth import Principal, current_principal
from admin_api.config import Settings
from admin_api.errors import ApiError
from admin_api.rooms import (
    RoomCallerNotActive,
    RoomCreationContext,
    RoomCreationInput,
    RoomLevelNotFound,
    RoomMembersNotActive,
    RoomRecord,
    RoomService,
    RoomStoreUnavailable,
    SynapseRoomAdminCompensator,
    SynapseRoomClient,
)

ADMIN_KEYCLOAK_ID = UUID("00000000-0000-0000-0000-000000000004")
CREATOR_ID = UUID("00000000-0000-0000-0000-000000000010")
MEMBER_ID = UUID("00000000-0000-0000-0000-000000000020")
ROOM_ID = "!room1:oryma.local"
CREATOR_MATRIX_ID = "@agent.demo1:oryma.local"
MEMBER_MATRIX_ID = "@agent.demo2:oryma.local"


def run(awaitable):
    return asyncio.run(awaitable)


def settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql://test",
        "keycloak_healthcheck_url": None,
        "synapse_healthcheck_url": None,
        "matrix_server_name": "oryma.local",
        "synapse_admin_access_token": "admin-test-token",
        "synapse_room_service_matrix_id": "@oryma-room-service:oryma.local",
        "synapse_room_service_access_token": "room-service-test-token",
    }
    values.update(overrides)
    return Settings(**values)


def principal() -> Principal:
    return Principal(str(ADMIN_KEYCLOAK_ID), frozenset({"agent"}))


def context() -> RoomCreationContext:
    return RoomCreationContext(
        actor_id=CREATOR_ID,
        creator_matrix_id=CREATOR_MATRIX_ID,
        member_matrix_ids=(MEMBER_MATRIX_ID,),
        level_code="CONFIDENTIEL",
        level_label="Confidentiel",
        retention_seconds=86_400,
    )


class FakeStore:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.creation: tuple[object, ...] | None = None
        self.finalized: tuple[RoomCreationContext, str, str] | None = None
        self.rooms = [
            RoomRecord(
                ROOM_ID,
                "[Confidentiel] Réunion DG",
                "CONFIDENTIEL",
                86_400,
                datetime(2026, 11, 2, tzinfo=UTC),
            )
        ]

    async def resolve_creation(self, caller_keycloak_id, member_ids, level_code):
        if self.error:
            raise self.error
        self.creation = (caller_keycloak_id, member_ids, level_code)
        return context()

    async def finalize_creation(self, room_context, room_id, room_name):
        if self.error:
            raise self.error
        self.finalized = (room_context, room_id, room_name)

    async def list_levels(self, caller_keycloak_id):
        if self.error:
            raise self.error
        return [
            {
                "code": "CONFIDENTIEL",
                "libelle": "Confidentiel",
                "duree_vie_secondes": 86_400,
            }
        ]

    async def list_rooms(self, caller_keycloak_id, after_room_id, limit):
        if self.error:
            raise self.error
        records = [
            room for room in self.rooms if after_room_id is None or room.room_id > after_room_id
        ]
        return records[:limit]

    async def record_pending_deletion(self, room_id):
        if self.error:
            raise self.error


class FakeCreator:
    def __init__(
        self,
        *,
        create_error: Exception | None = None,
        leave_error: Exception | None = None,
    ) -> None:
        self.create_error = create_error
        self.leave_error = leave_error
        self.spec = None
        self.left: list[str] = []

    async def create_room(self, spec, /):
        self.spec = spec
        if self.create_error:
            raise self.create_error
        return ROOM_ID

    async def leave_room(self, room_id, /):
        self.left.append(room_id)
        if self.leave_error:
            raise self.leave_error


class FakeCompensator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.deleted: list[str] = []

    async def delete_room(self, room_id, /):
        self.deleted.append(room_id)
        if self.error:
            raise self.error


def test_room_service_creates_room_and_persists_audit_record() -> None:
    store = FakeStore()
    creator = FakeCreator()
    compensator = FakeCompensator()
    service = RoomService(settings(), store, creator, compensator, store)

    result = run(
        service.create_room(
            principal(),
            RoomCreationInput(
                nom="Réunion DG",
                niveau="CONFIDENTIEL",
                membres=[MEMBER_ID],
            ),
        )
    )

    assert result == {
        "room_id": ROOM_ID,
        "nom": "[Confidentiel] Réunion DG",
        "niveau": "CONFIDENTIEL",
        "duree_vie_secondes": 86_400,
    }
    assert creator.spec.name == "[Confidentiel] Réunion DG"
    assert creator.spec.creator_matrix_id == CREATOR_MATRIX_ID
    assert creator.spec.member_matrix_ids == (MEMBER_MATRIX_ID,)
    assert creator.spec.retention_seconds == 86_400
    assert creator.left == [ROOM_ID]
    assert store.finalized == (context(), ROOM_ID, "[Confidentiel] Réunion DG")
    assert compensator.deleted == []


@pytest.mark.parametrize(
    ("level_code", "expected_seconds"),
    [
        ("DIFFUSION_RESTREINTE", 300),
        ("CONFIDENTIEL", 120),
    ],
)
def test_demo_retention_is_applied_and_persisted_as_snapshot(
    level_code: str,
    expected_seconds: int,
) -> None:
    store = FakeStore()
    creator = FakeCreator()
    demo_context = context()
    store.resolve_creation = lambda *_args: _return_context(demo_context, level_code)
    service = RoomService(settings(demo_retention=True), store, creator, FakeCompensator(), store)

    run(
        service.create_room(
            principal(),
            RoomCreationInput(nom="Test", niveau=level_code),
        )
    )

    assert creator.spec.retention_seconds == expected_seconds
    assert store.finalized[0].retention_seconds == expected_seconds


async def _return_context(original: RoomCreationContext, level_code: str) -> RoomCreationContext:
    return RoomCreationContext(
        actor_id=original.actor_id,
        creator_matrix_id=original.creator_matrix_id,
        member_matrix_ids=original.member_matrix_ids,
        level_code=level_code,
        level_label=(
            "Diffusion restreinte" if level_code == "DIFFUSION_RESTREINTE" else "Confidentiel"
        ),
        retention_seconds=604_800 if level_code == "DIFFUSION_RESTREINTE" else 86_400,
    )


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (RoomCallerNotActive(), "ERR-042"),
        (RoomMembersNotActive(), "ERR-042"),
        (RoomLevelNotFound(), "ERR-041"),
        (RoomStoreUnavailable(), "ERR-500"),
    ],
)
def test_room_service_rejects_invalid_creation_context(
    failure: Exception,
    expected_code: str,
) -> None:
    service = RoomService(settings(), FakeStore(error=failure))

    with pytest.raises(ApiError) as raised:
        run(
            service.create_room(
                principal(),
                RoomCreationInput(nom="Test", niveau="CONFIDENTIEL"),
            )
        )

    assert raised.value.code == expected_code


def test_room_service_compensates_if_service_account_cannot_leave() -> None:
    store = FakeStore()
    creator = FakeCreator(leave_error=rooms.RoomSynapseUnavailable())
    compensator = FakeCompensator()
    service = RoomService(settings(), store, creator, compensator, store)

    with pytest.raises(ApiError) as raised:
        run(
            service.create_room(
                principal(),
                RoomCreationInput(nom="Test", niveau="CONFIDENTIEL"),
            )
        )

    assert raised.value.code == "ERR-043"
    assert creator.left == [ROOM_ID]
    assert compensator.deleted == [ROOM_ID]
    assert store.finalized is None


def test_room_service_exposes_reconciliation_if_compensation_fails() -> None:
    store = FakeStore()

    async def fail_finalize(*_args):
        raise RoomStoreUnavailable

    store.finalize_creation = fail_finalize
    compensator = FakeCompensator(error=RuntimeError("delete failed"))
    service = RoomService(settings(), store, FakeCreator(), compensator, store)

    with pytest.raises(ApiError) as raised:
        run(
            service.create_room(
                principal(),
                RoomCreationInput(nom="Test", niveau="CONFIDENTIEL"),
            )
        )

    assert raised.value.code == "ERR-043"
    assert raised.value.details["room_id"] == ROOM_ID
    assert raised.value.details["reconciliation"] == "enregistree"


def test_room_service_lists_levels_and_only_callers_rooms() -> None:
    store = FakeStore()
    service = RoomService(settings(), store)

    levels = run(service.list_levels(principal()))
    rooms_list = run(service.list_rooms(principal()))

    assert levels[0]["code"] == "CONFIDENTIEL"
    assert rooms_list["items"][0]["room_id"] == ROOM_ID
    assert rooms_list["items"][0]["duree_vie_secondes"] == 86_400
    assert rooms_list["next_cursor"] is None


def test_room_list_uses_opaque_cursor_and_returns_next_page() -> None:
    store = FakeStore()
    store.rooms.append(
        RoomRecord(
            "!room2:oryma.local",
            "[Confidentiel] Réunion RH",
            "CONFIDENTIEL",
            86_400,
            datetime(2026, 11, 3, tzinfo=UTC),
        )
    )
    service = RoomService(settings(), store)

    first_page = run(service.list_rooms(principal(), page_size=1))
    second_page = run(
        service.list_rooms(principal(), cursor=first_page["next_cursor"], page_size=1)
    )

    assert first_page["items"][0]["room_id"] == ROOM_ID
    assert isinstance(first_page["next_cursor"], str)
    assert second_page["items"][0]["room_id"] == "!room2:oryma.local"
    assert second_page["next_cursor"] is None


def test_room_list_rejects_malformed_cursor() -> None:
    with pytest.raises(ApiError) as raised:
        run(RoomService(settings(), FakeStore()).list_rooms(principal(), cursor="bad"))

    assert raised.value.status_code == 422
    assert raised.value.code == "ERR-023"


def test_room_creation_input_rejects_duplicate_members() -> None:
    with pytest.raises(ValueError, match="doublons"):
        RoomCreationInput(
            nom="Test",
            niveau="CONFIDENTIEL",
            membres=[MEMBER_ID, MEMBER_ID],
        )


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("false", False)])
def test_demo_retention_environment_flag(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("DEMO_RETENTION", value)

    assert Settings.from_environment().demo_retention is expected


def test_synapse_room_client_creates_encrypted_private_room_and_leaves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/account/whoami"):
            return httpx.Response(
                200,
                json={"user_id": "@oryma-room-service:oryma.local"},
            )
        if request.url.path.endswith("/createRoom"):
            return httpx.Response(200, json={"room_id": ROOM_ID})
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(rooms.httpx, "AsyncClient", mock_client)
    client = SynapseRoomClient(settings())
    room_spec = rooms.RoomCreationSpec(
        name="[Confidentiel] Réunion DG",
        creator_matrix_id=CREATOR_MATRIX_ID,
        member_matrix_ids=(MEMBER_MATRIX_ID,),
        retention_seconds=86_400,
    )

    assert run(client.create_room(room_spec)) == ROOM_ID
    run(client.leave_room(ROOM_ID))

    create_request = requests[1]
    payload = json.loads(create_request.content)
    initial_state = {event["type"]: event["content"] for event in payload["initial_state"]}
    assert payload["visibility"] == "private"
    assert payload["preset"] == "private_chat"
    assert payload["invite"] == [CREATOR_MATRIX_ID, MEMBER_MATRIX_ID]
    assert initial_state["m.room.encryption"]["algorithm"] == "m.megolm.v1.aes-sha2"
    assert initial_state["m.room.retention"]["max_lifetime"] == 86_400_000
    assert initial_state["m.room.power_levels"]["users"][CREATOR_MATRIX_ID] == 100
    assert initial_state["m.room.power_levels"]["users"]["@oryma-room-service:oryma.local"] == 100
    assert [request.method for request in requests] == ["GET", "POST", "POST"]
    assert requests[2].url.path.endswith(f"/rooms/{ROOM_ID}/leave")
    assert all(
        request.headers["Authorization"] == "Bearer room-service-test-token" for request in requests
    )


def test_synapse_admin_compensator_deletes_room_and_purges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"kicked_users": []})

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(rooms.httpx, "AsyncClient", mock_client)
    run(SynapseRoomAdminCompensator(settings()).delete_room(ROOM_ID))

    assert requests[0].method == "DELETE"
    assert requests[0].url.path.endswith(f"/_synapse/admin/v1/rooms/{ROOM_ID}")
    assert json.loads(requests[0].content) == {"block": False, "purge": True}
    assert requests[0].headers["Authorization"] == "Bearer admin-test-token"


def test_synapse_room_client_rejects_token_for_unexpected_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"user_id": "@other:oryma.local"})

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(rooms.httpx, "AsyncClient", mock_client)
    room_spec = rooms.RoomCreationSpec(
        name="[Confidentiel] Réunion",
        creator_matrix_id=CREATOR_MATRIX_ID,
        member_matrix_ids=(),
        retention_seconds=120,
    )

    with pytest.raises(rooms.RoomSynapseUnavailable):
        run(SynapseRoomClient(settings()).create_room(room_spec))

    assert len(requests) == 1
    assert requests[0].url.path.endswith("/account/whoami")


def test_rooms_http_routes_return_contract_envelopes() -> None:
    app = main.create_app(settings())
    app.state.room_service = RoomService(settings(), FakeStore(), FakeCreator(), FakeCompensator())
    app.dependency_overrides[current_principal] = lambda: principal()

    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return (
                await client.get("/api/v1/levels"),
                await client.get("/api/v1/rooms"),
                await client.post(
                    "/api/v1/rooms",
                    json={"nom": "Réunion DG", "niveau": "CONFIDENTIEL", "membres": []},
                ),
            )

    levels_response, rooms_response, create_response = run(send())

    assert levels_response.status_code == 200
    assert levels_response.json()["data"][0]["code"] == "CONFIDENTIEL"
    assert rooms_response.status_code == 200
    assert rooms_response.json()["data"]["items"][0]["room_id"] == ROOM_ID
    assert rooms_response.json()["data"]["next_cursor"] is None
    assert create_response.status_code == 201
    assert create_response.json()["data"]["room_id"] == ROOM_ID
    assert create_response.json()["request_id"] == create_response.headers["X-Request-ID"]
