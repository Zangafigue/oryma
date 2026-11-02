import base64
import binascii
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from urllib.parse import quote, urlsplit
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from admin_api.auth import Principal, require_roles
from admin_api.config import Settings
from admin_api.errors import ApiError

router = APIRouter(prefix="/api/v1")
_DEMO_RETENTION_SECONDS = {
    "DIFFUSION_RESTREINTE": 300,
    "CONFIDENTIEL": 120,
}


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

    async def leave_room(self, room_id: str, /) -> None: ...


class RoomCompensator(Protocol):
    async def delete_room(self, room_id: str, /) -> None: ...


class RoomReconciliationRecorder(Protocol):
    async def record_pending_deletion(self, room_id: str, /) -> None: ...


@dataclass(frozen=True)
class RoomCreationContext:
    actor_id: UUID
    creator_matrix_id: str
    member_matrix_ids: tuple[str, ...]
    level_code: str
    level_label: str
    retention_seconds: int


@dataclass(frozen=True)
class RoomRecord:
    room_id: str
    name: str
    level_code: str
    retention_seconds: int
    created_at: datetime

    def as_response(self) -> dict[str, object]:
        return {
            "room_id": self.room_id,
            "nom": self.name,
            "niveau": self.level_code,
            "duree_vie_secondes": self.retention_seconds,
            "cree_le": self.created_at,
        }


class RoomStore(Protocol):
    async def resolve_creation(
        self,
        caller_keycloak_id: UUID,
        member_ids: tuple[UUID, ...],
        level_code: str,
    ) -> RoomCreationContext: ...

    async def finalize_creation(
        self,
        context: RoomCreationContext,
        room_id: str,
        room_name: str,
    ) -> None: ...

    async def list_levels(self, caller_keycloak_id: UUID) -> list[dict[str, object]]: ...

    async def list_rooms(
        self,
        caller_keycloak_id: UUID,
        after_room_id: str | None,
        limit: int,
    ) -> list[RoomRecord]: ...


class RoomStoreUnavailable(Exception):
    pass


class RoomCallerNotActive(Exception):
    pass


class RoomMembersNotActive(Exception):
    pass


class RoomLevelNotFound(Exception):
    pass


class RoomSynapseUnavailable(Exception):
    pass


class PostgresRoomStore:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    async def resolve_creation(
        self,
        caller_keycloak_id: UUID,
        member_ids: tuple[UUID, ...],
        level_code: str,
    ) -> RoomCreationContext:
        connection = await self._connect()
        try:
            actor = await connection.fetchrow(
                """
                SELECT id, matrix_id
                FROM agents
                WHERE keycloak_id = $1 AND statut = 'actif'
                """,
                caller_keycloak_id,
            )
            if actor is None:
                raise RoomCallerNotActive

            level = await connection.fetchrow(
                """
                SELECT code, libelle, duree_vie_secondes
                FROM niveaux_classification
                WHERE code = $1
                """,
                level_code,
            )
            if level is None:
                raise RoomLevelNotFound

            invited_member_ids = tuple(
                agent_id for agent_id in member_ids if agent_id != actor["id"]
            )
            if invited_member_ids:
                rows = await connection.fetch(
                    """
                    SELECT id, matrix_id
                    FROM agents
                    WHERE id = ANY($1::uuid[]) AND statut = 'actif'
                    """,
                    list(invited_member_ids),
                )
                if len(rows) != len(invited_member_ids):
                    raise RoomMembersNotActive
                members_by_id = {row["id"]: row["matrix_id"] for row in rows}
                matrix_ids = tuple(members_by_id[agent_id] for agent_id in invited_member_ids)
            else:
                matrix_ids = ()

            return RoomCreationContext(
                actor_id=actor["id"],
                creator_matrix_id=actor["matrix_id"],
                member_matrix_ids=matrix_ids,
                level_code=level["code"],
                level_label=level["libelle"],
                retention_seconds=int(level["duree_vie_secondes"]),
            )
        except (
            RoomCallerNotActive,
            RoomMembersNotActive,
            RoomLevelNotFound,
        ):
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise RoomStoreUnavailable from error
        finally:
            await connection.close()

    async def finalize_creation(
        self,
        context: RoomCreationContext,
        room_id: str,
        room_name: str,
    ) -> None:
        connection = await self._connect()
        try:
            async with connection.transaction():
                actor_is_active = await connection.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM agents WHERE id = $1 AND statut = 'actif')",
                    context.actor_id,
                )
                if not actor_is_active:
                    raise RoomCallerNotActive
                if context.member_matrix_ids:
                    active_member_count = await connection.fetchval(
                        """
                        SELECT count(*)
                        FROM agents
                        WHERE matrix_id = ANY($1::text[]) AND statut = 'actif'
                        """,
                        list(context.member_matrix_ids),
                    )
                    if active_member_count != len(context.member_matrix_ids):
                        raise RoomMembersNotActive

                await connection.execute(
                    """
                    INSERT INTO salles (
                        room_id, nom, niveau, duree_vie_secondes, cree_par
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    room_id,
                    room_name,
                    context.level_code,
                    context.retention_seconds,
                    context.actor_id,
                )
                await connection.execute(
                    """
                    INSERT INTO audit_log (acteur_id, action, cible_id, details)
                    VALUES ($1, 'CREATION_SALLE', $1, $2::jsonb)
                    """,
                    context.actor_id,
                    json.dumps(
                        {
                            "room_id": room_id,
                            "niveau": context.level_code,
                            "duree_vie_secondes": context.retention_seconds,
                        }
                    ),
                )
        except (RoomCallerNotActive, RoomMembersNotActive):
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise RoomStoreUnavailable from error
        finally:
            await connection.close()

    async def list_levels(self, caller_keycloak_id: UUID) -> list[dict[str, object]]:
        connection = await self._connect()
        try:
            await self._require_active_agent(connection, caller_keycloak_id)
            rows = await connection.fetch(
                """
                SELECT code, libelle, duree_vie_secondes, transfert_interdit
                FROM niveaux_classification
                ORDER BY code
                """
            )
            return [
                {
                    "code": row["code"],
                    "libelle": row["libelle"],
                    "duree_vie_secondes": int(row["duree_vie_secondes"]),
                }
                for row in rows
            ]
        except RoomCallerNotActive:
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise RoomStoreUnavailable from error
        finally:
            await connection.close()

    async def list_rooms(
        self,
        caller_keycloak_id: UUID,
        after_room_id: str | None,
        limit: int,
    ) -> list[RoomRecord]:
        connection = await self._connect()
        try:
            actor_id = await self._require_active_agent(connection, caller_keycloak_id)
            rows = await connection.fetch(
                """
                SELECT room_id, nom, niveau, duree_vie_secondes, cree_le
                FROM salles
                WHERE cree_par = $1 AND ($2::text IS NULL OR room_id > $2)
                ORDER BY room_id
                LIMIT $3
                """,
                actor_id,
                after_room_id,
                limit,
            )
            return [
                RoomRecord(
                    room_id=row["room_id"],
                    name=row["nom"],
                    level_code=row["niveau"],
                    retention_seconds=int(row["duree_vie_secondes"]),
                    created_at=row["cree_le"],
                )
                for row in rows
            ]
        except RoomCallerNotActive:
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise RoomStoreUnavailable from error
        finally:
            await connection.close()

    async def record_pending_deletion(self, room_id: str, /) -> None:
        connection = await self._connect()
        try:
            await connection.execute(
                """
                INSERT INTO reconciliation_salles (room_id)
                VALUES ($1)
                ON CONFLICT (room_id) DO NOTHING
                """,
                room_id,
            )
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise RoomStoreUnavailable from error
        finally:
            await connection.close()

    async def _connect(self) -> asyncpg.Connection:
        if not self._database_url:
            raise RoomStoreUnavailable("Database is not configured")
        try:
            return await asyncpg.connect(
                self._database_url,
                timeout=3,
                command_timeout=8,
            )
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise RoomStoreUnavailable from error

    @staticmethod
    async def _require_active_agent(
        connection: asyncpg.Connection,
        caller_keycloak_id: UUID,
    ) -> UUID:
        actor_id = await connection.fetchval(
            """
            SELECT id FROM agents
            WHERE keycloak_id = $1 AND statut = 'actif'
            """,
            caller_keycloak_id,
        )
        if actor_id is None:
            raise RoomCallerNotActive
        return actor_id


class SynapseRoomClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.synapse_client_api_url.rstrip("/")
        self._access_token = settings.synapse_room_service_access_token
        self._service_user_id = settings.synapse_room_service_matrix_id
        parts = urlsplit(self._base_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("Synapse Client API URL must be an absolute HTTP URL")

    async def create_room(self, spec: RoomCreationSpec, /) -> str:
        client = self._client()
        user_levels = {self._service_user_id: 100, spec.creator_matrix_id: 100}
        body = {
            "visibility": "private",
            "preset": "private_chat",
            "name": spec.name,
            "invite": [spec.creator_matrix_id, *spec.member_matrix_ids],
            "initial_state": [
                {
                    "type": "m.room.encryption",
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                },
                {
                    "type": "m.room.retention",
                    "state_key": "",
                    "content": {"max_lifetime": spec.retention_seconds * 1000},
                },
                {
                    "type": "m.room.power_levels",
                    "state_key": "",
                    "content": {
                        "ban": 50,
                        "events_default": 0,
                        "invite": 50,
                        "kick": 50,
                        "redact": 50,
                        "state_default": 50,
                        "users": user_levels,
                        "users_default": 0,
                    },
                },
            ],
        }
        try:
            async with client:
                response = await client.get(f"{self._base_url}/_matrix/client/v3/account/whoami")
                self._require_status(response, 200)
                identity = response.json()
                if (
                    not isinstance(identity, dict)
                    or identity.get("user_id") != self._service_user_id
                ):
                    raise ValueError("Synapse room service token belongs to another account")
                response = await client.post(
                    f"{self._base_url}/_matrix/client/v3/createRoom",
                    json=body,
                )
                self._require_status(response, 200)
                payload = response.json()
                room_id = payload.get("room_id") if isinstance(payload, dict) else None
                if not isinstance(room_id, str) or not room_id.startswith("!"):
                    raise ValueError("Synapse returned an invalid room id")
                return room_id
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise RoomSynapseUnavailable from error

    async def leave_room(self, room_id: str, /) -> None:
        client = self._client()
        try:
            async with client:
                response = await client.post(
                    f"{self._base_url}/_matrix/client/v3/rooms/{quote(room_id, safe='')}/leave",
                    json={},
                )
                self._require_status(response, 200)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise RoomSynapseUnavailable from error

    def _client(self) -> httpx.AsyncClient:
        if not self._access_token or not self._service_user_id:
            raise RoomSynapseUnavailable("Synapse room service credentials are not configured")
        return httpx.AsyncClient(
            timeout=15,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

    @staticmethod
    def _require_status(response: httpx.Response, expected_status: int) -> None:
        if response.status_code != expected_status:
            raise httpx.HTTPStatusError(
                f"Unexpected Synapse Client API status: {response.status_code}",
                request=response.request,
                response=response,
            )


class SynapseRoomAdminCompensator:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.synapse_admin_api_url.rstrip("/")
        self._access_token = settings.synapse_admin_access_token

    async def delete_room(self, room_id: str, /) -> None:
        if not self._access_token:
            raise RoomSynapseUnavailable("Synapse admin access token is not configured")
        try:
            async with httpx.AsyncClient(
                timeout=60,
                headers={"Authorization": f"Bearer {self._access_token}"},
            ) as client:
                response = await client.request(
                    "DELETE",
                    f"{self._base_url}/_synapse/admin/v1/rooms/{quote(room_id, safe='')}",
                    json={"block": False, "purge": True},
                )
                if response.status_code == 404:
                    return
                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Unexpected Synapse Admin API status: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
        except httpx.HTTPError as error:
            raise RoomSynapseUnavailable from error


class RoomCreationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str = Field(min_length=1, max_length=200, strict=True)
    niveau: str = Field(min_length=1, max_length=64, strict=True)
    membres: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("nom")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le nom de salle ne peut pas être vide.")
        return value.strip()

    @field_validator("membres")
    @classmethod
    def members_must_be_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("La liste des membres contient des doublons.")
        return value


class RoomService:
    def __init__(
        self,
        settings: Settings,
        store: RoomStore | None = None,
        creator: RoomCreator | None = None,
        compensator: RoomCompensator | None = None,
        reconciliation_recorder: RoomReconciliationRecorder | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or PostgresRoomStore(settings.database_url)
        self._creator = creator or SynapseRoomClient(settings)
        self._compensator = compensator or SynapseRoomAdminCompensator(settings)
        self._reconciliation_recorder = reconciliation_recorder or PostgresRoomStore(
            settings.database_url
        )

    async def list_levels(self, principal: Principal) -> list[dict[str, object]]:
        caller_id = self._caller_id(principal)
        try:
            return await self._store.list_levels(caller_id)
        except RoomCallerNotActive as error:
            raise self._inactive_agent_error() from error
        except RoomStoreUnavailable as error:
            raise self._unavailable_error() from error

    async def create_room(
        self,
        principal: Principal,
        request: RoomCreationInput,
    ) -> dict[str, object]:
        caller_id = self._caller_id(principal)
        try:
            context = await self._store.resolve_creation(
                caller_id,
                tuple(request.membres),
                request.niveau,
            )
            if self._settings.demo_retention:
                context = RoomCreationContext(
                    actor_id=context.actor_id,
                    creator_matrix_id=context.creator_matrix_id,
                    member_matrix_ids=context.member_matrix_ids,
                    level_code=context.level_code,
                    level_label=context.level_label,
                    retention_seconds=_DEMO_RETENTION_SECONDS.get(
                        context.level_code,
                        context.retention_seconds,
                    ),
                )
        except RoomCallerNotActive as error:
            raise self._inactive_agent_error() from error
        except RoomMembersNotActive as error:
            raise self._inactive_member_error() from error
        except RoomLevelNotFound as error:
            raise ApiError(
                status_code=422,
                code="ERR-041",
                message="Le niveau de classification demandé est inconnu.",
            ) from error
        except RoomStoreUnavailable as error:
            raise self._unavailable_error() from error

        room_name = f"[{context.level_label}] {request.nom}"
        spec = RoomCreationSpec(
            name=room_name,
            creator_matrix_id=context.creator_matrix_id,
            member_matrix_ids=context.member_matrix_ids,
            retention_seconds=context.retention_seconds,
        )

        async def finalize(room_id: str) -> dict[str, object]:
            await self._store.finalize_creation(context, room_id, room_name)
            return {
                "room_id": room_id,
                "nom": room_name,
                "niveau": context.level_code,
                "duree_vie_secondes": context.retention_seconds,
            }

        try:
            _, result = await create_room_with_compensation(
                self._creator,
                self._compensator,
                self._reconciliation_recorder,
                spec,
                finalize,
                after_create=self._creator.leave_room,
            )
            return result
        except RoomCompensationFailed as error:
            raise ApiError(
                status_code=502,
                code="ERR-043",
                message="La salle créée n’a pas pu être finalisée ni supprimée.",
                details={
                    "room_id": error.room_id,
                    "reconciliation": (
                        "enregistree" if error.reconciliation_error is None else "echec"
                    ),
                },
            ) from error
        except (RoomSynapseUnavailable, RoomStoreUnavailable) as error:
            raise self._creation_error() from error
        except RoomCallerNotActive as error:
            raise self._inactive_agent_error() from error
        except RoomMembersNotActive as error:
            raise self._inactive_member_error() from error

    async def list_rooms(
        self,
        principal: Principal,
        cursor: str | None = None,
        page_size: int = 50,
    ) -> dict[str, object]:
        caller_id = self._caller_id(principal)
        after_room_id = self._decode_cursor(cursor)
        try:
            records = await self._store.list_rooms(caller_id, after_room_id, page_size + 1)
        except RoomCallerNotActive as error:
            raise self._inactive_agent_error() from error
        except RoomStoreUnavailable as error:
            raise self._unavailable_error() from error
        has_more = len(records) > page_size
        page = records[:page_size]
        return {
            "items": [record.as_response() for record in page],
            "next_cursor": self._encode_cursor(page[-1].room_id) if has_more and page else None,
        }

    @staticmethod
    def _decode_cursor(cursor: str | None) -> str | None:
        if cursor is None:
            return None
        try:
            padded_cursor = cursor + "=" * (-len(cursor) % 4)
            room_id = base64.b64decode(
                padded_cursor,
                altchars=b"-_",
                validate=True,
            ).decode("utf-8")
            if not room_id.startswith("!") or ":" not in room_id:
                raise ValueError("Invalid room cursor")
            return room_id
        except (binascii.Error, UnicodeDecodeError, ValueError) as error:
            raise ApiError(
                status_code=422,
                code="ERR-023",
                message="Le curseur de pagination est invalide.",
            ) from error

    @staticmethod
    def _encode_cursor(room_id: str) -> str:
        return base64.urlsafe_b64encode(room_id.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _caller_id(principal: Principal) -> UUID:
        try:
            return UUID(principal.subject)
        except ValueError as error:
            raise ApiError(
                status_code=401,
                code="ERR-013",
                message="Jeton absent, invalide ou expiré.",
            ) from error

    @staticmethod
    def _inactive_agent_error() -> ApiError:
        return ApiError(
            status_code=422,
            code="ERR-042",
            message="L’agent demandeur n’est pas actif dans le registre.",
        )

    @staticmethod
    def _inactive_member_error() -> ApiError:
        return ApiError(
            status_code=422,
            code="ERR-042",
            message="Un membre demandé n’est pas un agent actif.",
        )

    @staticmethod
    def _creation_error() -> ApiError:
        return ApiError(
            status_code=502,
            code="ERR-043",
            message="La création de la salle a échoué ; aucune salle partielle n’est enregistrée.",
        )

    @staticmethod
    def _unavailable_error() -> ApiError:
        return ApiError(
            status_code=503,
            code="ERR-500",
            message="Le service des salles est temporairement indisponible.",
        )


def _service_from_request(request: Request) -> RoomService:
    return request.app.state.room_service


@router.get("/levels")
async def list_levels(
    request: Request,
    principal: Annotated[Principal, Depends(require_roles("agent", "admin"))],
    service: Annotated[RoomService, Depends(_service_from_request)],
) -> dict[str, object]:
    return {
        "data": await service.list_levels(principal),
        "request_id": request.state.request_id,
    }


@router.post("/rooms", status_code=201)
async def create_room(
    payload: RoomCreationInput,
    request: Request,
    principal: Annotated[Principal, Depends(require_roles("agent", "admin"))],
    service: Annotated[RoomService, Depends(_service_from_request)],
) -> dict[str, object]:
    return {
        "data": await service.create_room(principal, payload),
        "request_id": request.state.request_id,
    }


@router.get("/rooms")
async def list_rooms(
    request: Request,
    principal: Annotated[Principal, Depends(require_roles("agent", "admin"))],
    service: Annotated[RoomService, Depends(_service_from_request)],
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> dict[str, object]:
    return {
        "data": await service.list_rooms(principal, cursor, page_size),
        "request_id": request.state.request_id,
    }


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
    after_create: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[str, T]:
    room_id = await creator.create_room(spec)
    try:
        if after_create is not None:
            await after_create(room_id)
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
