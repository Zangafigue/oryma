import json
import secrets
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.errors import ApiError

AgentRole = Literal["admin", "agent"]
_REQUIRED_ACTIONS = ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]
_TEMPORARY_PASSWORD_BYTES = 24

router = APIRouter(prefix="/api/v1")


class EnrollmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifiant: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9._-]+$",
        strict=True,
    )
    nom_complet: str = Field(min_length=1, max_length=200, strict=True)
    ministere_code: str = Field(min_length=1, max_length=64, strict=True)
    fonction: str | None = Field(default=None, max_length=200, strict=True)
    role: AgentRole


@dataclass(frozen=True)
class EnrollmentContext:
    creator_id: UUID
    ministere_id: int


class EnrollmentStore(Protocol):
    async def resolve_context(
        self,
        creator_keycloak_id: UUID,
        ministere_code: str,
        matrix_id: str,
    ) -> EnrollmentContext: ...

    async def save_agent(
        self,
        context: EnrollmentContext,
        keycloak_id: UUID,
        matrix_id: str,
        nom_complet: str,
        fonction: str | None,
        role: AgentRole,
    ) -> UUID: ...


class IdentityProvider(Protocol):
    async def create_user(
        self,
        identifiant: str,
        nom_complet: str,
        role: AgentRole,
        mot_de_passe_temporaire: str,
    ) -> UUID: ...

    async def delete_user(self, keycloak_id: UUID) -> None: ...


class EnrollmentCallerNotAdmin(Exception):
    pass


class EnrollmentMinistryNotFound(Exception):
    pass


class EnrollmentConflict(Exception):
    pass


class EnrollmentUnavailable(Exception):
    pass


class IdentityProviderUserExists(Exception):
    pass


class IdentityProviderUnavailable(Exception):
    pass


class IdentityCompensationFailed(Exception):
    pass


class PostgresEnrollmentStore:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    async def resolve_context(
        self,
        creator_keycloak_id: UUID,
        ministere_code: str,
        matrix_id: str,
    ) -> EnrollmentContext:
        connection = await self._connect()
        try:
            creator_id = await connection.fetchval(
                """
                SELECT id
                FROM agents
                WHERE keycloak_id = $1 AND role = 'admin' AND statut = 'actif'
                """,
                creator_keycloak_id,
            )
            if creator_id is None:
                raise EnrollmentCallerNotAdmin

            ministere_id = await connection.fetchval(
                "SELECT id FROM ministeres WHERE code = $1",
                ministere_code,
            )
            if ministere_id is None:
                raise EnrollmentMinistryNotFound

            exists = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM agents WHERE matrix_id = $1)",
                matrix_id,
            )
            if exists:
                raise EnrollmentConflict
            return EnrollmentContext(creator_id=creator_id, ministere_id=ministere_id)
        except (EnrollmentCallerNotAdmin, EnrollmentMinistryNotFound, EnrollmentConflict):
            raise
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise EnrollmentUnavailable from error
        finally:
            await connection.close()

    async def save_agent(
        self,
        context: EnrollmentContext,
        keycloak_id: UUID,
        matrix_id: str,
        nom_complet: str,
        fonction: str | None,
        role: AgentRole,
    ) -> UUID:
        connection = await self._connect()
        try:
            async with connection.transaction():
                agent_id = await connection.fetchval(
                    """
                    INSERT INTO agents (
                        keycloak_id, matrix_id, nom_complet, ministere_id,
                        fonction, role, cree_par
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    keycloak_id,
                    matrix_id,
                    nom_complet,
                    context.ministere_id,
                    fonction,
                    role,
                    context.creator_id,
                )
                await connection.execute(
                    """
                    INSERT INTO audit_log (acteur_id, action, cible_id, details)
                    VALUES ($1, 'ENROLEMENT', $2, $3::jsonb)
                    """,
                    context.creator_id,
                    agent_id,
                    json.dumps({"role": role}),
                )
            return agent_id
        except asyncpg.UniqueViolationError as error:
            raise EnrollmentConflict from error
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise EnrollmentUnavailable from error
        finally:
            await connection.close()

    async def _connect(self) -> asyncpg.Connection:
        if not self._database_url:
            raise EnrollmentUnavailable("Database is not configured")
        try:
            return await asyncpg.connect(
                self._database_url,
                timeout=3,
                command_timeout=5,
            )
        except (asyncpg.PostgresError, OSError, TimeoutError) as error:
            raise EnrollmentUnavailable from error


class KeycloakAdminClient:
    def __init__(self, settings: Settings) -> None:
        self._issuer = (settings.oidc_issuer or "").rstrip("/")
        self._client_id = settings.keycloak_admin_client_id
        self._client_secret = settings.keycloak_admin_client_secret
        admin_issuer = self._internal_issuer_from_jwks(settings.oidc_jwks_url) or self._issuer
        issuer_parts = urlsplit(admin_issuer)
        realm_path, separator, realm = issuer_parts.path.rpartition("/realms/")
        if not separator or not realm:
            self._token_url = ""
            self._admin_base_url = ""
        else:
            authority = f"{issuer_parts.scheme}://{issuer_parts.netloc}"
            self._token_url = f"{authority}{issuer_parts.path}/protocol/openid-connect/token"
            self._admin_base_url = f"{authority}{realm_path}/admin/realms/{realm}"

    async def create_user(
        self,
        identifiant: str,
        nom_complet: str,
        role: AgentRole,
        mot_de_passe_temporaire: str,
    ) -> UUID:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                token = await self._service_token(client)
                headers = {"Authorization": f"Bearer {token}"}
                enrollment_marker = str(uuid4())
                try:
                    response = await client.post(
                        f"{self._admin_base_url}/users",
                        headers=headers,
                        json={
                            "username": identifiant,
                            "enabled": True,
                            "firstName": nom_complet,
                            "requiredActions": _REQUIRED_ACTIONS,
                            "attributes": {"oryma_enrollment_id": [enrollment_marker]},
                        },
                    )
                except httpx.HTTPError as error:
                    await self._compensate_uncertain_user(
                        client,
                        headers,
                        identifiant,
                        enrollment_marker,
                    )
                    raise IdentityProviderUnavailable from error
                if response.status_code == 409:
                    raise IdentityProviderUserExists
                if response.status_code >= 500:
                    await self._compensate_uncertain_user(
                        client,
                        headers,
                        identifiant,
                        enrollment_marker,
                    )
                    raise IdentityProviderUnavailable
                self._require_status(response, 201)
                try:
                    keycloak_id = self._user_id_from_location(response.headers.get("Location"))
                except ValueError as error:
                    await self._compensate_uncertain_user(
                        client,
                        headers,
                        identifiant,
                        enrollment_marker,
                    )
                    raise IdentityProviderUnavailable from error

                try:
                    await self._set_temporary_password(
                        client,
                        headers,
                        keycloak_id,
                        mot_de_passe_temporaire,
                    )
                    await self._assign_realm_role(client, headers, keycloak_id, role)
                except Exception as error:
                    try:
                        await self._delete_user(client, headers, keycloak_id)
                    except Exception as compensation_error:
                        raise IdentityCompensationFailed from compensation_error
                    raise IdentityProviderUnavailable from error
                return keycloak_id
        except (
            IdentityProviderUserExists,
            IdentityProviderUnavailable,
            IdentityCompensationFailed,
        ):
            raise
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise IdentityProviderUnavailable from error

    async def delete_user(self, keycloak_id: UUID) -> None:
        async with httpx.AsyncClient(timeout=8) as client:
            token = await self._service_token(client)
            await self._delete_user(
                client,
                {"Authorization": f"Bearer {token}"},
                keycloak_id,
            )

    async def _delete_user_by_username(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        identifiant: str,
        enrollment_marker: str,
    ) -> None:
        response = await client.get(
            f"{self._admin_base_url}/users",
            headers=headers,
            params={"username": identifiant, "exact": "true"},
        )
        self._require_status(response, 200)
        users = response.json()
        if not isinstance(users, list):
            raise ValueError("Keycloak returned an invalid user list")
        for user in users:
            if (
                isinstance(user, dict)
                and user.get("username") == identifiant
                and isinstance(user.get("id"), str)
                and isinstance(user.get("attributes"), dict)
                and user["attributes"].get("oryma_enrollment_id") == [enrollment_marker]
            ):
                await self._delete_user(client, headers, UUID(user["id"]))
                return

    async def _compensate_uncertain_user(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        identifiant: str,
        enrollment_marker: str,
    ) -> None:
        try:
            await self._delete_user_by_username(
                client,
                headers,
                identifiant,
                enrollment_marker,
            )
        except Exception as error:
            raise IdentityCompensationFailed from error

    async def _service_token(self, client: httpx.AsyncClient) -> str:
        if not self._token_url or not self._admin_base_url or not self._client_secret:
            raise IdentityProviderUnavailable("Keycloak admin client is not configured")
        try:
            response = await client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            self._require_status(response, 200)
            token = response.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("Keycloak returned no access token")
            return token
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise IdentityProviderUnavailable from error

    async def _set_temporary_password(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        keycloak_id: UUID,
        password: str,
    ) -> None:
        response = await client.put(
            f"{self._admin_base_url}/users/{keycloak_id}/reset-password",
            headers=headers,
            json={"type": "password", "value": password, "temporary": True},
        )
        self._require_status(response, 204)

    async def _assign_realm_role(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        keycloak_id: UUID,
        role_name: AgentRole,
    ) -> None:
        response = await client.get(
            f"{self._admin_base_url}/roles/{role_name}",
            headers=headers,
        )
        self._require_status(response, 200)
        role = response.json()
        if not isinstance(role, dict) or role.get("name") != role_name:
            raise ValueError("Keycloak returned an invalid realm role")
        response = await client.post(
            f"{self._admin_base_url}/users/{keycloak_id}/role-mappings/realm",
            headers=headers,
            json=[role],
        )
        self._require_status(response, 204)

    async def _delete_user(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        keycloak_id: UUID,
    ) -> None:
        response = await client.delete(
            f"{self._admin_base_url}/users/{keycloak_id}",
            headers=headers,
        )
        if response.status_code == 404:
            return
        self._require_status(response, 204)

    @staticmethod
    def _user_id_from_location(location: str | None) -> UUID:
        if not location:
            raise ValueError("Keycloak user creation response has no Location header")
        try:
            return UUID(location.rstrip("/").rsplit("/", 1)[-1])
        except ValueError as error:
            raise ValueError("Keycloak returned an invalid user identifier") from error

    @staticmethod
    def _require_status(response: httpx.Response, expected_status: int) -> None:
        if response.status_code != expected_status:
            raise httpx.HTTPStatusError(
                f"Unexpected Keycloak status: {response.status_code}",
                request=response.request,
                response=response,
            )

    @staticmethod
    def _internal_issuer_from_jwks(jwks_url: str | None) -> str | None:
        if not jwks_url:
            return None
        parts = urlsplit(jwks_url)
        suffix = "/protocol/openid-connect/certs"
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or not parts.path.endswith(suffix)
        ):
            return None
        return f"{parts.scheme}://{parts.netloc}{parts.path.removesuffix(suffix)}"


class EnrollmentService:
    def __init__(
        self,
        settings: Settings,
        store: EnrollmentStore | None = None,
        identity_provider: IdentityProvider | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or PostgresEnrollmentStore(settings.database_url)
        self._identity_provider = identity_provider or KeycloakAdminClient(settings)

    async def enroll(
        self,
        principal: Principal,
        request: EnrollmentInput,
    ) -> dict[str, object]:
        try:
            creator_keycloak_id = UUID(principal.subject)
        except ValueError as error:
            raise ApiError(
                status_code=401,
                code="ERR-013",
                message="Jeton absent, invalide ou expiré.",
            ) from error

        matrix_server_name = self._settings.matrix_server_name
        if not matrix_server_name and self._settings.oidc_issuer:
            matrix_server_name = urlsplit(self._settings.oidc_issuer).hostname
        if not matrix_server_name:
            raise self._unavailable_error()
        matrix_id = f"@{request.identifiant}:{matrix_server_name}"

        try:
            context = await self._store.resolve_context(
                creator_keycloak_id,
                request.ministere_code,
                matrix_id,
            )
        except EnrollmentCallerNotAdmin as error:
            raise ApiError(
                status_code=403,
                code="ERR-014",
                message="Seul un administrateur actif peut enrôler un agent.",
            ) from error
        except EnrollmentMinistryNotFound as error:
            raise ApiError(
                status_code=404,
                code="ERR-021",
                message="Le ministère demandé est introuvable.",
            ) from error
        except EnrollmentConflict as error:
            raise self._conflict_error() from error
        except EnrollmentUnavailable as error:
            raise self._unavailable_error() from error

        temporary_password = secrets.token_urlsafe(_TEMPORARY_PASSWORD_BYTES)
        try:
            keycloak_id = await self._identity_provider.create_user(
                request.identifiant,
                request.nom_complet,
                request.role,
                temporary_password,
            )
        except IdentityProviderUserExists as error:
            raise self._conflict_error() from error
        except IdentityCompensationFailed as error:
            raise self._compensation_error() from error
        except IdentityProviderUnavailable as error:
            raise self._unavailable_error() from error

        try:
            agent_id = await self._store.save_agent(
                context,
                keycloak_id,
                matrix_id,
                request.nom_complet,
                request.fonction,
                request.role,
            )
        except EnrollmentConflict as error:
            await self._compensate(keycloak_id)
            raise self._conflict_error() from error
        except EnrollmentUnavailable as error:
            await self._compensate(keycloak_id)
            raise self._unavailable_error() from error
        except Exception as error:
            await self._compensate(keycloak_id)
            raise self._unavailable_error() from error

        return {
            "id": str(agent_id),
            "identifiant": request.identifiant,
            "matrix_id": matrix_id,
            "nom_complet": request.nom_complet,
            "ministere_code": request.ministere_code,
            "fonction": request.fonction,
            "role": request.role,
            "statut": "actif",
            "mot_de_passe_temporaire": temporary_password,
        }

    async def _compensate(self, keycloak_id: UUID) -> None:
        try:
            await self._identity_provider.delete_user(keycloak_id)
        except Exception as error:
            raise self._compensation_error() from error

    @staticmethod
    def _conflict_error() -> ApiError:
        return ApiError(
            status_code=409,
            code="ERR-022",
            message="Cet identifiant est déjà utilisé.",
        )

    @staticmethod
    def _unavailable_error() -> ApiError:
        return ApiError(
            status_code=503,
            code="ERR-500",
            message="Une dépendance requise pour l’enrôlement est indisponible.",
        )

    @staticmethod
    def _compensation_error() -> ApiError:
        return ApiError(
            status_code=503,
            code="ERR-500",
            message="L’enrôlement a échoué et le compte Keycloak n’a pas pu être supprimé.",
            details={"compensation": "echec"},
        )


def _service_from_request(request: Request) -> EnrollmentService:
    return request.app.state.enrollment_service


@router.post("/agents", status_code=201)
async def enroll_agent(
    payload: EnrollmentInput,
    request: Request,
    principal: Annotated[Principal, Depends(require_admin)],
    service: Annotated[EnrollmentService, Depends(_service_from_request)],
) -> dict[str, object]:
    data = await service.enroll(principal, payload)
    return {"data": data, "request_id": request.state.request_id}
