import asyncio

import pytest

from admin_api.rooms import (
    RoomCompensationFailed,
    RoomCreationSpec,
    create_room_with_compensation,
)


class FakeCreator:
    def __init__(self) -> None:
        self.spec: RoomCreationSpec | None = None

    async def create_room(self, spec: RoomCreationSpec, /) -> str:
        self.spec = spec
        return "!room:oryma.local"


class FakeCompensator:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.deleted: list[str] = []

    async def delete_room(self, room_id: str, /) -> None:
        self.deleted.append(room_id)
        if self.error:
            raise self.error


class FakeReconciliationRecorder:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.pending: list[str] = []

    async def record_pending_deletion(self, room_id: str, /) -> None:
        self.pending.append(room_id)
        if self.error:
            raise self.error


def create_spec() -> RoomCreationSpec:
    return RoomCreationSpec(
        name="[Confidentiel] Réunion DG",
        creator_matrix_id="@admin:oryma.local",
        member_matrix_ids=("@agent:oryma.local",),
        retention_seconds=86_400,
    )


def test_creation_finalizes_without_compensation() -> None:
    creator = FakeCreator()
    compensator = FakeCompensator()
    recorder = FakeReconciliationRecorder()

    async def finalize(room_id: str) -> str:
        return f"saved:{room_id}"

    result = asyncio.run(
        create_room_with_compensation(creator, compensator, recorder, create_spec(), finalize)
    )

    assert result == ("!room:oryma.local", "saved:!room:oryma.local")
    assert creator.spec == create_spec()
    assert compensator.deleted == []
    assert recorder.pending == []


def test_finalization_failure_deletes_created_room_and_reraises() -> None:
    creator = FakeCreator()
    compensator = FakeCompensator()
    recorder = FakeReconciliationRecorder()
    failure = RuntimeError("database transaction failed")

    async def finalize(_room_id: str) -> str:
        raise failure

    with pytest.raises(RuntimeError, match="database transaction failed"):
        asyncio.run(
            create_room_with_compensation(creator, compensator, recorder, create_spec(), finalize)
        )

    assert compensator.deleted == ["!room:oryma.local"]
    assert recorder.pending == []


def test_failed_compensation_records_room_for_reconciliation() -> None:
    creator = FakeCreator()
    compensator = FakeCompensator(RuntimeError("delete failed"))
    recorder = FakeReconciliationRecorder()

    async def finalize(_room_id: str) -> str:
        raise RuntimeError("database transaction failed")

    with pytest.raises(RoomCompensationFailed) as raised:
        asyncio.run(
            create_room_with_compensation(creator, compensator, recorder, create_spec(), finalize)
        )

    assert raised.value.room_id == "!room:oryma.local"
    assert raised.value.reconciliation_error is None
    assert recorder.pending == ["!room:oryma.local"]


def test_failed_reconciliation_is_exposed_for_operational_logging() -> None:
    creator = FakeCreator()
    compensator = FakeCompensator(RuntimeError("delete failed"))
    recorder = FakeReconciliationRecorder(RuntimeError("database unavailable"))

    async def finalize(_room_id: str) -> str:
        raise RuntimeError("database transaction failed")

    with pytest.raises(RoomCompensationFailed) as raised:
        asyncio.run(
            create_room_with_compensation(creator, compensator, recorder, create_spec(), finalize)
        )

    assert raised.value.room_id == "!room:oryma.local"
    assert isinstance(raised.value.reconciliation_error, RuntimeError)
    assert str(raised.value.reconciliation_error) == "database unavailable"
    assert recorder.pending == ["!room:oryma.local"]


def test_room_creation_requires_positive_retention() -> None:
    with pytest.raises(ValueError, match="strictement positive"):
        RoomCreationSpec(
            name="[Confidentiel] Réunion DG",
            creator_matrix_id="@admin:oryma.local",
            member_matrix_ids=(),
            retention_seconds=0,
        )
