import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Request

from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.errors import ApiError

router = APIRouter(prefix="/api/v1")


@dataclass(frozen=True)
class AuditEvent:
    id: int
    action: str
    actor_id: UUID | None
    target_id: UUID | None
    details: dict[str, object] | None
    timestamp: datetime

    def as_response(self) -> dict[str, object]:
        return {
            "id": self.id,
            "action": self.action,
            "acteur_id": str(self.actor_id) if self.actor_id else None,
            "cible_id": str(self.target_id) if self.target_id else None,
            "details": self.details,
            "horodatage": self.timestamp,
        }


class AuditStore(Protocol):
    async def list_events(
        self,
        actor_id: UUID,
        action: str | None,
        actor_filter: UUID | None,
        since: datetime | None,
        until: datetime | None,
        after_id: int | None,
        limit: int,
    ) -> list[AuditEvent]: ...


class AuditCallerNotAdmin(Exception):
    pass


class AuditStoreUnavailable(Exception):
    pass


class PostgresAuditStore:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

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
        connection = await self._connect()
        try:
            is_active_admin = await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM agents
                    WHERE keycloak_id = $1 AND role = 'admin' AND statut = 'actif'
                )
                """,
                actor_id,
            )
            if not is_active_admin:
                raise AuditCallerNotAdmin

            rows = await connection.fetch(
                """
                SELECT id, action, acteur_id, cible_id, details, horodatage
                FROM audit_log
                WHERE ($1::text IS NULL OR action = $1)
                  AND ($2::uuid IS NULL OR acteur_id = $2)
                  AND ($3::timestamptz IS NULL OR horodatage >= $3)
                  AND ($4::timestamptz IS NULL OR horodatage <= $4)
                  AND ($5::bigint IS NULL OR id < $5)
                ORDER BY id DESC
                LIMIT $6
                """,
                action,
                actor_filter,
                since,
                until,
                after_id,
                limit,
            )
            return [
                AuditEvent(
                    id=int(row["id"]),
                    action=row["action"],
                    actor_id=row["acteur_id"],
                    target_id=row["cible_id"],
                    details=self._decode_details(row["details"]),
                    timestamp=row["horodatage"],
                )
                for row in rows
            ]
        except AuditCallerNotAdmin:
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise AuditStoreUnavailable from error
        finally:
            await connection.close()

    async def _connect(self) -> asyncpg.Connection:
        if not self._database_url:
            raise AuditStoreUnavailable("Database is not configured")
        try:
            return await asyncpg.connect(
                self._database_url,
                timeout=3,
                command_timeout=8,
            )
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise AuditStoreUnavailable from error

    @staticmethod
    def _decode_details(value: object) -> dict[str, object] | None:
        if value is None:
            return None
        details = json.loads(value) if isinstance(value, str) else value
        if not isinstance(details, dict):
            raise ValueError("Audit details are not a JSON object")
        return details


class AuditService:
    def __init__(self, settings: Settings, store: AuditStore | None = None) -> None:
        self._store = store or PostgresAuditStore(settings.database_url)

    async def list_events(
        self,
        principal: Principal,
        action: str | None,
        actor_filter: UUID | None,
        since: datetime | None,
        until: datetime | None,
        cursor: str | None,
        page_size: int,
    ) -> dict[str, object]:
        if since is not None and until is not None and since > until:
            raise ApiError(
                status_code=422,
                code="ERR-023",
                message="La date de début doit précéder la date de fin.",
                details={"champs": [{"champ": "depuis", "erreur": "date_range"}]},
            )
        actor_id = self._caller_id(principal)
        after_id = self._decode_cursor(cursor)
        try:
            events = await self._store.list_events(
                actor_id,
                action,
                actor_filter,
                since,
                until,
                after_id,
                page_size + 1,
            )
        except AuditCallerNotAdmin as error:
            raise ApiError(
                status_code=403,
                code="ERR-014",
                message="Seul un administrateur actif peut consulter le journal d’audit.",
            ) from error
        except AuditStoreUnavailable as error:
            raise ApiError(
                status_code=503,
                code="ERR-500",
                message="Le journal d’audit est temporairement indisponible.",
            ) from error

        has_more = len(events) > page_size
        page = events[:page_size]
        return {
            "items": [event.as_response() for event in page],
            "next_cursor": self._encode_cursor(page[-1].id) if has_more and page else None,
        }

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
    def _encode_cursor(event_id: int) -> str:
        raw = event_id.to_bytes(8, "big", signed=False)
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> int | None:
        if cursor is None:
            return None
        try:
            decoded = base64.b64decode(
                cursor + "=" * (-len(cursor) % 4),
                altchars=b"-_",
                validate=True,
            )
            if len(decoded) != 8:
                raise ValueError("Cursor has an invalid length")
            event_id = int.from_bytes(decoded, "big", signed=False)
            if event_id < 1:
                raise ValueError("Cursor has an invalid event id")
            return event_id
        except (binascii.Error, ValueError) as error:
            raise ApiError(
                status_code=422,
                code="ERR-023",
                message="Le curseur de pagination est invalide.",
                details={"champs": [{"champ": "cursor", "erreur": "value_error"}]},
            ) from error


def _service_from_request(request: Request) -> AuditService:
    return request.app.state.audit_service


@router.get("/audit")
async def list_audit_events(
    request: Request,
    principal: Annotated[Principal, Depends(require_admin)],
    service: Annotated[AuditService, Depends(_service_from_request)],
    action: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    acteur_id: UUID | None = None,
    depuis: datetime | None = None,
    jusqu_a: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=32)] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, object]:
    data = await service.list_events(
        principal,
        action,
        acteur_id,
        depuis,
        jusqu_a,
        cursor,
        page_size,
    )
    return {"data": data, "request_id": request.state.request_id}
