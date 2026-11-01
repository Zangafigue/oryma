import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from jwt import PyJWK

from admin_api import auth, main
from admin_api.auth import JwksClient, Principal, require_admin
from admin_api.config import Settings

ISSUER = "https://oryma.local/auth/realms/oryma"
AUDIENCE = "admin-api"


def test_settings_load_keycloak_contract_without_confusing_service_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYCLOAK_ISSUER", ISSUER)
    monkeypatch.setenv(
        "KEYCLOAK_JWKS_INTERNAL_URL",
        "http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs",
    )
    monkeypatch.setenv("KEYCLOAK_ADMIN_CLIENT_ID", "admin-api")
    monkeypatch.setenv("KEYCLOAK_ADMIN_CLIENT_SECRET", "service-client-secret")
    monkeypatch.setenv("OIDC_CLIENT_ID", "admin-api")

    settings = Settings.from_environment()

    assert settings.oidc_issuer == ISSUER
    assert settings.oidc_jwks_url == (
        "http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs"
    )
    assert settings.oidc_audience == AUDIENCE
    assert settings.oidc_client_id == "console"


@pytest.fixture
def signing_key() -> tuple[Any, PyJWK]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    return private_key, PyJWK.from_dict(public_jwk, algorithm="RS256")


def build_token(private_key: Any, **claim_overrides: Any) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "demo-user-id",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
        "azp": "console",
        "typ": "Bearer",
        "realm_access": {"roles": ["agent"]},
    }
    claims.update(claim_overrides)
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def make_app() -> FastAPI:
    app = main.create_app(
        Settings(
            database_url="postgresql://test",
            keycloak_healthcheck_url=None,
            synapse_healthcheck_url=None,
            oidc_issuer=ISSUER,
            oidc_audience=AUDIENCE,
            oidc_jwks_url="http://keycloak/jwks",
        )
    )

    @app.get("/api/v1/admin/test")
    async def admin_route(
        principal: Annotated[Principal, Depends(require_admin)],
    ) -> dict[str, str]:
        return {"subject": principal.subject}

    return app


def request_admin(app: FastAPI, token: str | None) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            return await client.get("/api/v1/admin/test", headers=headers)

    return asyncio.run(send_request())


def install_signing_key(
    monkeypatch: pytest.MonkeyPatch,
    signing_jwk: PyJWK,
) -> None:
    async def get_signing_key(_client: JwksClient, _key_id: str) -> PyJWK:
        return signing_jwk

    monkeypatch.setattr(JwksClient, "get_signing_key", get_signing_key)


def test_admin_access_accepts_valid_token_and_realm_role(
    monkeypatch: pytest.MonkeyPatch,
    signing_key: tuple[Any, PyJWK],
) -> None:
    private_key, public_jwk = signing_key
    install_signing_key(monkeypatch, public_jwk)

    response = request_admin(
        make_app(), build_token(private_key, realm_access={"roles": ["admin"]})
    )

    assert response.status_code == 200
    assert response.json() == {"subject": "demo-user-id"}


@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"iss": "https://wrong.example/realm"},
        {"aud": "another-api"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"azp": "another-client"},
        {"typ": "ID"},
    ],
)
def test_admin_access_rejects_invalid_token_claims(
    monkeypatch: pytest.MonkeyPatch,
    signing_key: tuple[Any, PyJWK],
    claim_overrides: dict[str, Any],
) -> None:
    private_key, public_jwk = signing_key
    install_signing_key(monkeypatch, public_jwk)

    response = request_admin(make_app(), build_token(private_key, **claim_overrides))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ERR-013"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_missing_bearer_token_is_rejected() -> None:
    response = request_admin(make_app(), None)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ERR-013"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_jwks_client_loads_and_caches_public_signing_keys(
    monkeypatch: pytest.MonkeyPatch,
    signing_key: tuple[Any, PyJWK],
) -> None:
    _, public_jwk = signing_key
    jwk_data = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_jwk.key))
    jwk_data.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    requests: list[str] = []

    def handle_jwks(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json={"keys": [jwk_data]})

    transport = httpx.MockTransport(handle_jwks)
    original_client = httpx.AsyncClient

    def mock_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(auth.httpx, "AsyncClient", mock_client)
    jwks = JwksClient("http://keycloak/jwks")

    async def load_keys() -> tuple[PyJWK, PyJWK]:
        return await jwks.get_signing_key("test-key"), await jwks.get_signing_key("test-key")

    first, second = asyncio.run(load_keys())

    assert first.key == second.key
    assert requests == ["http://keycloak/jwks"]


def test_role_refusal_is_audited_with_only_route_and_reason(
    monkeypatch: pytest.MonkeyPatch,
    signing_key: tuple[Any, PyJWK],
) -> None:
    private_key, public_jwk = signing_key
    install_signing_key(monkeypatch, public_jwk)
    audit_entries: list[tuple[Settings, str, str]] = []

    async def record_refusal(settings: Settings, route: str, reason: str) -> None:
        audit_entries.append((settings, route, reason))

    monkeypatch.setattr(auth, "record_refused_access", record_refusal)
    response = request_admin(
        make_app(),
        build_token(private_key, realm_access={"roles": ["agent"]}),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ERR-014"
    assert len(audit_entries) == 1
    _, route, reason = audit_entries[0]
    assert route == "/api/v1/admin/test"
    assert reason == "ROLE_INSUFFISANT"


def test_refused_role_returns_service_error_if_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
    signing_key: tuple[Any, PyJWK],
) -> None:
    private_key, public_jwk = signing_key
    install_signing_key(monkeypatch, public_jwk)

    async def audit_unavailable(settings: Settings, route: str, reason: str) -> None:
        assert settings.database_url == "postgresql://test"
        assert route == "/api/v1/admin/test"
        assert reason == "ROLE_INSUFFISANT"
        raise auth.AuditUnavailable

    monkeypatch.setattr(auth, "record_refused_access", audit_unavailable)
    response = request_admin(
        make_app(),
        build_token(private_key, realm_access={"roles": ["agent"]}),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ERR-500"
