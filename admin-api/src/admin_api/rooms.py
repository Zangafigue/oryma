from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RoomCreationSpec:
    name: str
    creator_matrix_id: str
    member_matrix_ids: tuple[str, ...]
    retention_seconds: int

    def __post_init__(self) -> None:
        if self.retention_seconds <= 0:
            raise ValueError("La durée de rétention doit être strictement positive.")


class RoomCreator(Protocol):
    async def create_room(self, spec: RoomCreationSpec, /) -> str: ...


class RoomCompensator(Protocol):
    async def delete_room(self, room_id: str, /) -> None: ...


class RoomReconciliationRecorder(Protocol):
    async def record_pending_deletion(self, room_id: str, /) -> None: ...


class RoomCompensationFailed(RuntimeError):
    def __init__(
        self,
        room_id: str,
        finalization_error: Exception,
        deletion_error: Exception,
        reconciliation_error: Exception | None,
    ) -> None:
        super().__init__("La salle créée n'a pas pu être supprimée après un échec.")
        self.room_id = room_id
        self.finalization_error = finalization_error
        self.deletion_error = deletion_error
        self.reconciliation_error = reconciliation_error


async def create_room_with_compensation[T](
    creator: RoomCreator,
    compensator: RoomCompensator,
    reconciliation_recorder: RoomReconciliationRecorder,
    spec: RoomCreationSpec,
    finalize: Callable[[str], Awaitable[T]],
) -> tuple[str, T]:
    room_id = await creator.create_room(spec)
    try:
        result = await finalize(room_id)
    except Exception as finalization_error:
        try:
            await compensator.delete_room(room_id)
        except Exception as deletion_error:
            try:
                await reconciliation_recorder.record_pending_deletion(room_id)
            except Exception as reconciliation_error:
                raise RoomCompensationFailed(
                    room_id,
                    finalization_error,
                    deletion_error,
                    reconciliation_error,
                ) from deletion_error
            raise RoomCompensationFailed(
                room_id,
                finalization_error,
                deletion_error,
                None,
            ) from deletion_error
        raise
    return room_id, result
