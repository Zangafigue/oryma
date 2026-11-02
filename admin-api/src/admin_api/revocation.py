import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Protocol
from urllib.parse import quote, urlsplit
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Request

from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.enrollment import (
    IdentityProviderUnavailable,
    KeycloakAdminClient,
)
from admin_api.errors import ApiError

router = APIRouter(prefix="/api/v1")

_STEPS = (
    "keycloak_desactivation",
    "keycloak_sessions",
    "synapse_appareils",
    "synapse_desactivation",
    "base_statut",
    "audit",
)


@dataclass(frozen=True)
class RevocationTarget:
    agent_id: UUID
    keycloak_id: UUID
    matrix_id: str


@dataclass(frozen=True)
class RevocationRun:
    target: RevocationTarget
    actor_id: UUID
    completed_steps: frozenset[int]
    legacy_already_revoked: bool
    mark_step_completed: Callable[[int], Awaitable[None]]


@dataclass(frozen=True)
class RevocationStepResult:
    ordre: int
    nom: str
    statut: str
    detail: str | None = None

    def as_response(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ordre": self.ordre,
            "nom": self.nom,
            "statut": self.statut,
        }
        if self.detail is not None:
            result["detail"] = self.detail
        return result


@dataclass(frozen=True)
class RevocationResult:
    agent_id: UUID
    complete: bool
    steps: tuple[RevocationStepResult, ...]

    def as_response(self) -> dict[str, object]:
        return {
            "agent_id": str(self.agent_id),
            "statut_operation": "complete" if self.complete else "incomplete",
            "etapes": [step.as_response() for step in self.steps],
        }


class RevocationCallerNotAdmin(Exception):
    pass


class RevocationAgentNotFound(Exception):
    pass


class RevocationAlreadyRunning(Exception):
    pass


class RevocationUnavailable(Exception):
    pass


class SynapseAdminUnavailable(Exception):
    pass


class RevocationStore(Protocol):
    async def execute(
        self,
        caller_keycloak_id: UUID,
        agent_id: UUID,
        handler: Callable[[RevocationRun], Awaitable[RevocationResult]],
    ) -> RevocationResult: ...


class KeycloakRevoker(Protocol):
    async def disable_user(self, keycloak_id: UUID) -> None: ...

    async def logout_user_sessions(self, keycloak_id: UUID) -> None: ...


class SynapseRevoker(Protocol):
    async def delete_all_devices(self, matrix_id: str) -> None: ...

    async def deactivate_user(self, matrix_id: str) -> None: ...


class SynapseAdminClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.synapse_admin_api_url.rstrip("/")
        self._access_token = settings.synapse_admin_access_token
        parts = urlsplit(self._base_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("Synapse Admin API URL must be an absolute HTTP URL")

    async def delete_all_devices(self, matrix_id: str) -> None:
        client = self._client()
        user_path = quote(matrix_id, safe="")
        try:
            async with client:
                response = await client.get(
                    f"{self._base_url}/_synapse/admin/v2/users/{user_path}/devices"
                )
                if response.status_code == 404:
                    return
                self._require_status(response, 200)
                payload = response.json()
                devices = payload.get("devices") if isinstance(payload, dict) else None
                if not isinstance(devices, list):
                    raise ValueError("Synapse returned an invalid device list")
                device_ids: list[str] = []
                for device in devices:
                    if not isinstance(device, dict) or not isinstance(device.get("device_id"), str):
                        raise ValueError("Synapse returned an invalid device")
                    device_ids.append(device["device_id"])

                for device_id in device_ids:
                    encoded_device_id = quote(device_id, safe="")
                    response = await client.request(
                        "DELETE",
                        f"{self._base_url}/_synapse/admin/v2/users/{user_path}"
                        f"/devices/{encoded_device_id}",
                        json={},
                    )
                    self._require_status(response, 200)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise SynapseAdminUnavailable from error

    async def deactivate_user(self, matrix_id: str) -> None:
        client = self._client()
        user_path = quote(matrix_id, safe="")
        try:
            async with client:
                response = await client.get(f"{self._base_url}/_synapse/admin/v2/users/{user_path}")
                if response.status_code == 404:
                    return
                self._require_status(response, 200)
                user = response.json()
                if not isinstance(user, dict):
                    raise ValueError("Synapse returned an invalid user record")
                if user.get("deactivated") is True:
                    return
                response = await client.post(
                    f"{self._base_url}/_synapse/admin/v1/deactivate/{user_path}",
                    json={"erase": False},
                )
                self._require_status(response, 200)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise SynapseAdminUnavailable from error

    def _client(self) -> httpx.AsyncClient:
        if not self._access_token:
            raise SynapseAdminUnavailable("Synapse admin access token is not configured")
        return httpx.AsyncClient(
            timeout=10,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

    @staticmethod
    def _require_status(response: httpx.Response, expected_status: int) -> None:
        if response.status_code != expected_status:
            raise httpx.HTTPStatusError(
                f"Unexpected Synapse status: {response.status_code}",
                request=response.request,
                response=response,
            )


class PostgresRevocationStore:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    async def execute(
        self,
        caller_keycloak_id: UUID,
        agent_id: UUID,
        handler: Callable[[RevocationRun], Awaitable[RevocationResult]],
    ) -> RevocationResult:
        connection = await self._connect()
        lock_acquired = False
        try:
            lock_acquired = await connection.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
                str(agent_id),
            )
            if not lock_acquired:
                raise RevocationAlreadyRunning

            async with connection.transaction():
                actor_id = await self._active_admin_id(connection, caller_keycloak_id)
                target_row = await connection.fetchrow(
                    """
                    SELECT id, keycloak_id, matrix_id, statut
                    FROM agents
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    agent_id,
                )
                if target_row is None:
                    raise RevocationAgentNotFound

                revocation = await connection.fetchrow(
                    """
                    SELECT acteur_id
                    FROM agent_revocations
                    WHERE agent_id = $1
                    """,
                    agent_id,
                )
                if target_row["statut"] == "revoque" and revocation is None:
                    completed_steps = frozenset(range(1, 7))
                    stored_actor_id = actor_id
                    legacy_already_revoked = True
                else:
                    await connection.execute(
                        """
                        INSERT INTO agent_revocations (agent_id, acteur_id)
                        VALUES ($1, $2)
                        ON CONFLICT (agent_id) DO NOTHING
                        """,
                        agent_id,
                        actor_id,
                    )
                    stored_actor_id = await connection.fetchval(
                        "SELECT acteur_id FROM agent_revocations WHERE agent_id = $1",
                        agent_id,
                    )
                    step_rows = await connection.fetch(
                        """
                        SELECT ordre
                        FROM agent_revocation_steps
                        WHERE agent_id = $1
                        """,
                        agent_id,
                    )
                    completed_steps = frozenset(int(row["ordre"]) for row in step_rows)
                    legacy_already_revoked = False

            target = RevocationTarget(
                agent_id=agent_id,
                keycloak_id=target_row["keycloak_id"],
                matrix_id=target_row["matrix_id"],
            )

            async def mark_step_completed(order: int) -> None:
                if order not in range(1, 7):
                    raise ValueError("Invalid revocation step")
                async with connection.transaction():
                    if order == 5:
                        await connection.execute(
                            """
                            UPDATE agents
                            SET statut = 'revoque',
                                revoque_le = COALESCE(revoque_le, now()),
                                revoque_par = COALESCE(revoque_par, $2)
                            WHERE id = $1
                            """,
                            agent_id,
                            stored_actor_id,
                        )
                    elif order == 6:
                        await connection.execute(
                            """
                            INSERT INTO audit_log (acteur_id, action, cible_id, details)
                            VALUES ($1, 'REVOCATION', $2, $3::jsonb)
                            """,
                            stored_actor_id,
                            agent_id,
                            json.dumps({"etapes": list(range(1, 7))}),
                        )
                    await connection.execute(
                        """
                        INSERT INTO agent_revocation_steps (agent_id, ordre)
                        VALUES ($1, $2)
                        ON CONFLICT (agent_id, ordre) DO NOTHING
                        """,
                        agent_id,
                        order,
                    )
                    await connection.execute(
                        "UPDATE agent_revocations SET mis_a_jour_le = now() WHERE agent_id = $1",
                        agent_id,
                    )

            context = RevocationRun(
                target=target,
                actor_id=stored_actor_id,
                completed_steps=completed_steps,
                legacy_already_revoked=legacy_already_revoked,
                mark_step_completed=mark_step_completed,
            )
            return await handler(context)
        except (
            RevocationAlreadyRunning,
            RevocationCallerNotAdmin,
            RevocationAgentNotFound,
            RevocationUnavailable,
        ):
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError, ValueError, TypeError) as error:
            raise RevocationUnavailable from error
        finally:
            try:
                if lock_acquired:
                    await connection.execute(
                        "SELECT pg_advisory_unlock(hashtextextended($1, 0))",
                        str(agent_id),
                    )
            finally:
                await connection.close()

    async def _connect(self) -> asyncpg.Connection:
        if not self._database_url:
            raise RevocationUnavailable("Database is not configured")
        try:
            return await asyncpg.connect(
                self._database_url,
                timeout=3,
                command_timeout=8,
            )
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise RevocationUnavailable from error

    @staticmethod
    async def _active_admin_id(
        connection: asyncpg.Connection,
        caller_keycloak_id: UUID,
    ) -> UUID:
        actor_id = await connection.fetchval(
            """
            SELECT id FROM agents
            WHERE keycloak_id = $1 AND role = 'admin' AND statut = 'actif'
            """,
            caller_keycloak_id,
        )
        if actor_id is None:
            raise RevocationCallerNotAdmin
        return actor_id


class RevocationService:
    def __init__(
        self,
        settings: Settings,
        store: RevocationStore | None = None,
        keycloak: KeycloakRevoker | None = None,
        synapse: SynapseRevoker | None = None,
    ) -> None:
        self._store = store or PostgresRevocationStore(settings.database_url)
        self._keycloak = keycloak or KeycloakAdminClient(settings)
        self._synapse = synapse or SynapseAdminClient(settings)

    async def revoke(self, principal: Principal, agent_id: UUID) -> dict[str, object]:
        try:
            caller_keycloak_id = UUID(principal.subject)
        except ValueError as error:
            raise ApiError(
                status_code=401,
                code="ERR-013",
                message="Jeton absent, invalide ou expiré.",
            ) from error

        try:
            result = await self._store.execute(
                caller_keycloak_id,
                agent_id,
                self._run_steps,
            )
        except RevocationCallerNotAdmin as error:
            raise ApiError(
                status_code=403,
                code="ERR-014",
                message="Seul un administrateur actif peut révoquer un agent.",
            ) from error
        except RevocationAgentNotFound as error:
            raise ApiError(
                status_code=404,
                code="ERR-031",
                message="L’agent demandé est introuvable.",
            ) from error
        except RevocationAlreadyRunning as error:
            raise ApiError(
                status_code=409,
                code="ERR-034",
                message="Une révocation de cet agent est déjà en cours.",
            ) from error
        except RevocationUnavailable as error:
            raise self._unavailable_error() from error

        data = result.as_response()
        if not result.complete:
            raise ApiError(
                status_code=502,
                code="ERR-033",
                message=(
                    "La révocation est incomplète ; réessayez pour reprendre les étapes restantes."
                ),
                details=data,
            )
        return data

    async def _run_steps(self, run: RevocationRun) -> RevocationResult:
        if run.legacy_already_revoked:
            return RevocationResult(
                agent_id=run.target.agent_id,
                complete=True,
                steps=tuple(
                    RevocationStepResult(order, name, "reussie")
                    for order, name in enumerate(_STEPS, start=1)
                ),
            )

        actions: tuple[Callable[[], Awaitable[None]], ...] = (
            lambda: self._keycloak.disable_user(run.target.keycloak_id),
            lambda: self._keycloak.logout_user_sessions(run.target.keycloak_id),
            lambda: self._synapse.delete_all_devices(run.target.matrix_id),
            lambda: self._synapse.deactivate_user(run.target.matrix_id),
            self._no_op,
            self._no_op,
        )
        steps: list[RevocationStepResult] = []
        failed_step: int | None = None
        failure_detail: str | None = None

        for order, (name, action) in enumerate(zip(_STEPS, actions, strict=True), start=1):
            if order in run.completed_steps:
                steps.append(RevocationStepResult(order, name, "reussie"))
                continue
            if failed_step is not None:
                steps.append(RevocationStepResult(order, name, "ignoree"))
                continue
            try:
                await action()
            except (
                IdentityProviderUnavailable,
                SynapseAdminUnavailable,
            ):
                failed_step = order
                failure_detail = "dependance_indisponible"
                steps.append(RevocationStepResult(order, name, "echec", failure_detail))
                continue
            try:
                await run.mark_step_completed(order)
            except (
                RevocationUnavailable,
                asyncpg.PostgresError,
                OSError,
                TimeoutError,
            ):
                failed_step = order
                failure_detail = "persistance_indisponible"
                steps.append(RevocationStepResult(order, name, "echec", failure_detail))
                continue
            steps.append(RevocationStepResult(order, name, "reussie"))

        return RevocationResult(
            agent_id=run.target.agent_id,
            complete=failed_step is None,
            steps=tuple(steps),
        )

    @staticmethod
    async def _no_op() -> None:
        return None

    @staticmethod
    def _unavailable_error() -> ApiError:
        return ApiError(
            status_code=503,
            code="ERR-500",
            message="Le service de révocation est temporairement indisponible.",
        )


def _service_from_request(request: Request) -> RevocationService:
    return request.app.state.revocation_service


@router.post("/agents/{agent_id}/revoke")
async def revoke_agent(
    agent_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_admin)],
    service: Annotated[RevocationService, Depends(_service_from_request)],
) -> dict[str, object]:
    data = await service.revoke(principal, agent_id)
    return {"data": data, "request_id": request.state.request_id}
