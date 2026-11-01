import asyncio
import json
import time
from dataclasses import dataclass
from typing import Annotated

import asyncpg
import httpx
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK

from admin_api.config import Settings
from admin_api.errors import ApiError

_BEARER = HTTPBearer(auto_error=False)
_JWKS_CACHE_SECONDS = 300
_UNKNOWN_KEY_REFRESH_INTERVAL_SECONDS = 30
_JWKS_FAILURE_RETRY_SECONDS = 5
_ALLOWED_ALGORITHMS = ("RS256",)


class JwksUnavailable(Exception):
    pass


class AuditUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]


class JwksClient:
    def __init__(self, url: str) -> None:
        self._url = url
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = 0.0
        self._last_refresh_at = 0.0
        self._refresh_retry_at = 0.0
        self._lock = asyncio.Lock()

    async def get_signing_key(self, key_id: str) -> PyJWK:
        now = time.monotonic()
        key = self._keys.get(key_id)
        if key is not None and now < self._expires_at:
            return key

        async with self._lock:
            now = time.monotonic()
            if now >= self._expires_at:
                await self._refresh_with_backoff()
            key = self._keys.get(key_id)
            if (
                key is None
                and time.monotonic() - self._last_refresh_at
                >= _UNKNOWN_KEY_REFRESH_INTERVAL_SECONDS
            ):
                await self._refresh_with_backoff()
                key = self._keys.get(key_id)
        if key is None:
            raise jwt.InvalidTokenError("Unknown signing key")
        return key

    async def _refresh_with_backoff(self) -> None:
        if time.monotonic() < self._refresh_retry_at:
            raise JwksUnavailable("JWKS refresh is temporarily throttled")
        try:
            await self._refresh()
        except JwksUnavailable:
            self._refresh_retry_at = time.monotonic() + _JWKS_FAILURE_RETRY_SECONDS
            raise

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(self._url)
                response.raise_for_status()
            payload = response.json()
            jwks = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(jwks, list):
                raise ValueError("JWKS response has no keys list")

            keys: dict[str, PyJWK] = {}
            for jwk in jwks:
                if (
                    not isinstance(jwk, dict)
                    or jwk.get("kty") != "RSA"
                    or jwk.get("alg") != "RS256"
                    or jwk.get("use", "sig") != "sig"
                    or not isinstance(jwk.get("kid"), str)
                ):
                    continue
                if jwk["kid"] in keys:
                    raise ValueError("JWKS response contains a duplicate key identifier")
                keys[jwk["kid"]] = PyJWK.from_dict(jwk, algorithm="RS256")
            if not keys:
                raise ValueError("JWKS response contains no supported signing keys")
        except (httpx.HTTPError, ValueError, TypeError, jwt.PyJWTError) as error:
            raise JwksUnavailable from error

        self._keys = keys
        self._last_refresh_at = time.monotonic()
        self._expires_at = self._last_refresh_at + _JWKS_CACHE_SECONDS
        self._refresh_retry_at = 0.0


async def verify_access_token(token: str, settings: Settings, jwks: JwksClient) -> Principal:
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise JwksUnavailable("OIDC verification is not configured")

    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in _ALLOWED_ALGORITHMS:
            raise jwt.InvalidTokenError("Unsupported signing algorithm")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise jwt.InvalidTokenError("Missing signing key identifier")

        signing_key = await jwks.get_signing_key(key_id)
        claims = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=list(_ALLOWED_ALGORITHMS),
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except JwksUnavailable:
        raise
    except jwt.PyJWTError as error:
        raise ApiError(
            status_code=401,
            code="ERR-013",
            message="Jeton absent, invalide ou expiré.",
        ) from error

    subject = claims.get("sub")
    realm_access = claims.get("realm_access")
    roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
    if (
        not isinstance(subject, str)
        or not subject
        or claims.get("azp") != settings.oidc_client_id
        or claims.get("typ") != "Bearer"
        or not isinstance(roles, list)
        or any(not isinstance(role, str) for role in roles)
    ):
        raise ApiError(
            status_code=401,
            code="ERR-013",
            message="Jeton absent, invalide ou expiré.",
        )

    return Principal(subject=subject, roles=frozenset(roles))


async def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_BEARER)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="ERR-013",
            message="Jeton absent, invalide ou expiré.",
        )

    settings: Settings = request.app.state.settings
    try:
        return await verify_access_token(
            credentials.credentials,
            settings,
            request.app.state.jwks_client,
        )
    except JwksUnavailable as error:
        raise ApiError(
            status_code=503,
            code="ERR-500",
            message="Le fournisseur d’identité est temporairement indisponible.",
        ) from error


def require_roles(*allowed_roles: str):
    async def check_roles(
        request: Request,
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if principal.roles.isdisjoint(allowed_roles):
            settings: Settings = request.app.state.settings
            try:
                await record_refused_access(
                    settings,
                    route=request.url.path,
                    reason="ROLE_INSUFFISANT",
                )
            except AuditUnavailable as error:
                raise ApiError(
                    status_code=503,
                    code="ERR-500",
                    message="Le refus d’accès n’a pas pu être inscrit à l’audit.",
                ) from error
            raise ApiError(
                status_code=403,
                code="ERR-014",
                message="Rôle insuffisant pour cette opération.",
            )
        return principal

    return check_roles


async def record_refused_access(settings: Settings, route: str, reason: str) -> None:
    if not settings.database_url:
        raise AuditUnavailable("The audit database is not configured")

    details = json.dumps({"route": route, "motif": reason})
    try:
        connection = await asyncpg.connect(
            settings.database_url,
            timeout=2,
            command_timeout=2,
        )
        try:
            await connection.execute(
                """
                INSERT INTO audit_log (action, details)
                VALUES ('TENTATIVE_ACCES_REFUSE', $1::jsonb)
                """,
                details,
            )
        finally:
            await connection.close()
    except (asyncpg.PostgresError, OSError, TimeoutError, ValueError) as error:
        raise AuditUnavailable from error


require_admin = require_roles("admin")
