import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request

from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.errors import ApiError

AgentStatus = Literal["actif", "revoque"]
AgentRole = Literal["admin", "agent"]

router = APIRouter(prefix="/api/v1")


@dataclass(frozen=True)
class AgentRecord:
    id: UUID
    identifiant: str
    matrix_id: str
    nom_complet: str
    ministere_code: str | None
    fonction: str | None
    role: AgentRole
    statut: AgentStatus
    cree_le: datetime
    revoque_le: datetime | None

    def as_response(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "identifiant": self.identifiant,
            "matrix_id": self.matrix_id,
            "nom_complet": self.nom_complet,
            "ministere_code": self.ministere_code,
            "fonction": self.fonction,
            "role": self.role,
            "statut": self.statut,
            "cree_le": self.cree_le,
            "revoque_le": self.revoque_le,
        }


class AgentManagementCallerNotAdmin(Exception):
    pass


class AgentNotFound(Exception):
    pass


class AgentManagementUnavailable(Exception):
    pass


class AgentManagementStore(Protocol):
    async def list_agents(
        self,
        caller_id: UUID,
        status: AgentStatus | None,
        ministry_code: str | None,
        after_id: UUID | None,
        limit: int,
    ) -> list[AgentRecord]: ...

    async def get_agent(self, caller_id: UUID, agent_id: UUID) -> AgentRecord: ...


class PostgresAgentManagementStore:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    async def list_agents(
        self,
        caller_id: UUID,
        status: AgentStatus | None,
        ministry_code: str | None,
        after_id: UUID | None,
        limit: int,
    ) -> list[AgentRecord]:
        connection = await self._connect()
        try:
            await self._require_active_admin(connection, caller_id)
            rows = await connection.fetch(
                """
                SELECT a.id, a.matrix_id, a.nom_complet, m.code AS ministere_code,
                       a.fonction, a.role, a.statut, a.cree_le, a.revoque_le
                FROM agents AS a
                LEFT JOIN ministeres AS m ON m.id = a.ministere_id
                WHERE ($1::statut_agent IS NULL OR a.statut = $1)
                  AND ($2::text IS NULL OR m.code = $2)
                  AND ($3::uuid IS NULL OR a.id > $3)
                ORDER BY a.id
                LIMIT $4
                """,
                status,
                ministry_code,
                after_id,
                limit,
            )
            return [self._record_from_row(row) for row in rows]
        except AgentManagementCallerNotAdmin:
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise AgentManagementUnavailable from error
        finally:
            await connection.close()

    async def get_agent(self, caller_id: UUID, agent_id: UUID) -> AgentRecord:
        connection = await self._connect()
        try:
            await self._require_active_admin(connection, caller_id)
            row = await connection.fetchrow(
                """
                SELECT a.id, a.matrix_id, a.nom_complet, m.code AS ministere_code,
                       a.fonction, a.role, a.statut, a.cree_le, a.revoque_le
                FROM agents AS a
                LEFT JOIN ministeres AS m ON m.id = a.ministere_id
                WHERE a.id = $1
                """,
                agent_id,
            )
            if row is None:
                raise AgentNotFound
            return self._record_from_row(row)
        except (AgentManagementCallerNotAdmin, AgentNotFound):
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise AgentManagementUnavailable from error
        finally:
            await connection.close()

    async def _connect(self) -> asyncpg.Connection:
        if not self._database_url:
            raise AgentManagementUnavailable("Database is not configured")
        try:
            return await asyncpg.connect(
                self._database_url,
                timeout=3,
                command_timeout=5,
            )
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise AgentManagementUnavailable from error

    @staticmethod
    async def _require_active_admin(connection: asyncpg.Connection, caller_id: UUID) -> None:
        is_admin = await connection.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM agents
                WHERE keycloak_id = $1 AND role = 'admin' AND statut = 'actif'
            )
            """,
            caller_id,
        )
        if not is_admin:
            raise AgentManagementCallerNotAdmin

    @staticmethod
    def _record_from_row(row: asyncpg.Record) -> AgentRecord:
        matrix_id = row["matrix_id"]
        localpart, separator, _ = matrix_id[1:].partition(":")
        if not matrix_id.startswith("@") or not separator or not localpart:
            raise ValueError("Stored Matrix identifier is invalid")
        return AgentRecord(
            id=row["id"],
            identifiant=localpart,
            matrix_id=matrix_id,
            nom_complet=row["nom_complet"],
            ministere_code=row["ministere_code"],
            fonction=row["fonction"],
            role=row["role"],
            statut=row["statut"],
            cree_le=row["cree_le"],
            revoque_le=row["revoque_le"],
        )


class AgentManagementService:
    def __init__(
        self,
        settings: Settings,
        store: AgentManagementStore | None = None,
    ) -> None:
        self._store = store or PostgresAgentManagementStore(settings.database_url)

    async def list_agents(
        self,
        principal: Principal,
        status: AgentStatus | None,
        ministry_code: str | None,
        cursor: str | None,
        page_size: int,
    ) -> dict[str, object]:
        caller_id = self._caller_id(principal)
        after_id = self._decode_cursor(cursor)
        try:
            records = await self._store.list_agents(
                caller_id,
                status,
                ministry_code,
                after_id,
                page_size + 1,
            )
        except AgentManagementCallerNotAdmin as error:
            raise self._forbidden_error() from error
        except AgentManagementUnavailable as error:
            raise self._unavailable_error() from error

        has_more = len(records) > page_size
        page = records[:page_size]
        return {
            "items": [record.as_response() for record in page],
            "next_cursor": self._encode_cursor(page[-1].id) if has_more and page else None,
        }

    async def get_agent(self, principal: Principal, agent_id: UUID) -> dict[str, object]:
        caller_id = self._caller_id(principal)
        try:
            record = await self._store.get_agent(caller_id, agent_id)
        except AgentManagementCallerNotAdmin as error:
            raise self._forbidden_error() from error
        except AgentNotFound as error:
            raise ApiError(
                status_code=404,
                code="ERR-031",
                message="L’agent demandé est introuvable.",
            ) from error
        except AgentManagementUnavailable as error:
            raise self._unavailable_error() from error
        return record.as_response()

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
    def _encode_cursor(agent_id: UUID) -> str:
        return base64.urlsafe_b64encode(agent_id.bytes).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> UUID | None:
        if cursor is None:
            return None
        try:
            decoded = base64.b64decode(
                cursor + "=" * (-len(cursor) % 4),
                altchars=b"-_",
                validate=True,
            )
            if len(decoded) != 16:
                raise ValueError("Cursor has an invalid length")
            return UUID(bytes=decoded)
        except (binascii.Error, ValueError) as error:
            raise ApiError(
                status_code=422,
                code="ERR-023",
                message="Le curseur de pagination est invalide.",
                details={"champs": [{"champ": "cursor", "erreur": "value_error"}]},
            ) from error

    @staticmethod
    def _forbidden_error() -> ApiError:
        return ApiError(
            status_code=403,
            code="ERR-014",
            message="Seul un administrateur actif peut consulter les agents.",
        )

    @staticmethod
    def _unavailable_error() -> ApiError:
        return ApiError(
            status_code=503,
            code="ERR-500",
            message="Le service de gestion des agents est temporairement indisponible.",
        )


def _service_from_request(request: Request) -> AgentManagementService:
    return request.app.state.agent_management_service


@router.get("/agents")
async def list_agents(
    request: Request,
    principal: Annotated[Principal, Depends(require_admin)],
    service: Annotated[AgentManagementService, Depends(_service_from_request)],
    statut: AgentStatus | None = None,
    ministere_code: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, object]:
    data = await service.list_agents(principal, statut, ministere_code, cursor, page_size)
    return {"data": data, "request_id": request.state.request_id}


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_admin)],
    service: Annotated[AgentManagementService, Depends(_service_from_request)],
) -> dict[str, object]:
    data = await service.get_agent(principal, agent_id)
    return {"data": data, "request_id": request.state.request_id}
