import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from admin_api import enrollment, main
from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.enrollment import (
    EnrollmentConflict,
    EnrollmentContext,
    EnrollmentInput,
    EnrollmentMinistryNotFound,
    EnrollmentService,
    IdentityCompensationFailed,
    IdentityProviderUnavailable,
    IdentityProviderUserExists,
    KeycloakAdminClient,
)

ISSUER = "https://oryma.local/auth/realms/oryma"
ADMIN_ID = UUID("00000000-0000-0000-0000-000000000001")
KEYCLOAK_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
AGENT_ID = UUID("00000000-0000-0000-0000-000000000003")
ADMIN_SUBJECT = "00000000-0000-0000-0000-000000000004"


class FakeStore:
    def __init__(
        self,
        *,
        context_error: Exception | None = None,
        save_error: Exception | None = None,
    ) -> None:
        self.context_error = context_error
        self.save_error = save_error
        self.context_request: tuple[UUID, str, str] | None = None
        self.saved_agent: tuple[object, ...] | None = None

    async def resolve_context(
        self,
        creator_keycloak_id: UUID,
        ministere_code: str,
        matrix_id: str,
    ) -> EnrollmentContext:
        self.context_request = (creator_keycloak_id, ministere_code, matrix_id)
        if self.context_error:
            raise self.context_error
        return EnrollmentContext(creator_id=ADMIN_ID, ministere_id=7)

    async def save_agent(
        self,
        context: EnrollmentContext,
        keycloak_id: UUID,
        matrix_id: str,
        nom_complet: str,
        fonction: str | None,
        role: str,
    ) -> UUID:
        self.saved_agent = (
            context,
            keycloak_id,
            matrix_id,
            nom_complet,
            fonction,
            role,
        )
        if self.save_error:
            raise self.save_error
        return AGENT_ID


class FakeIdentityProvider:
    def __init__(
        self,
        *,
        create_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.create_error = create_error
        self.delete_error = delete_error
        self.created: tuple[str, str, str, str] | None = None
        self.deleted: list[UUID] = []

    async def create_user(
        self,
        identifiant: str,
        nom_complet: str,
        role: str,
        mot_de_passe_temporaire: str,
    ) -> UUID:
        self.created = (identifiant, nom_complet, role, mot_de_passe_temporaire)
        if self.create_error:
            raise self.create_error
        return KEYCLOAK_USER_ID

    async def delete_user(self, keycloak_id: UUID) -> None:
        self.deleted.append(keycloak_id)
        if self.delete_error:
            raise self.delete_error


def settings() -> Settings:
    return Settings(
        database_url="postgresql://test",
        keycloak_healthcheck_url=None,
        synapse_healthcheck_url=None,
        oidc_issuer=ISSUER,
        oidc_audience="admin-api",
        oidc_jwks_url=("http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs"),
        keycloak_admin_client_secret="test-only",
        matrix_server_name="oryma.local",
    )


def valid_request() -> EnrollmentInput:
    return EnrollmentInput(
        identifiant="agent.demo1",
        nom_complet="Agent Démo 1",
        ministere_code="MIN-DEMO-A",
        fonction="Chargé d’études",
        role="agent",
    )


def run(awaitable):
    return asyncio.run(awaitable)


def test_enrollment_returns_temporary_password_once_and_saves_no_password() -> None:
    store = FakeStore()
    identity = FakeIdentityProvider()
    service = EnrollmentService(settings(), store, identity)

    result = run(service.enroll(Principal(ADMIN_SUBJECT, frozenset({"admin"})), valid_request()))

    assert result["id"] == str(AGENT_ID)
    assert result["matrix_id"] == "@agent.demo1:oryma.local"
    assert result["mot_de_passe_temporaire"] == identity.created[3]
    assert len(identity.created[3]) >= 32
    assert store.context_request == (
        UUID(ADMIN_SUBJECT),
        "MIN-DEMO-A",
        "@agent.demo1:oryma.local",
    )
    assert store.saved_agent == (
        EnrollmentContext(creator_id=ADMIN_ID, ministere_id=7),
        KEYCLOAK_USER_ID,
        "@agent.demo1:oryma.local",
        "Agent Démo 1",
        "Chargé d’études",
        "agent",
    )
    assert identity.deleted == []


@pytest.mark.parametrize(
    ("context_error", "status_code", "error_code"),
    [
        (EnrollmentMinistryNotFound(), 404, "ERR-021"),
        (EnrollmentConflict(), 409, "ERR-022"),
    ],
)
def test_enrollment_prechecks_fail_before_keycloak_creation(
    context_error: Exception,
    status_code: int,
    error_code: str,
) -> None:
    service = EnrollmentService(
        settings(),
        FakeStore(context_error=context_error),
        identity := FakeIdentityProvider(),
    )

    with pytest.raises(enrollment.ApiError) as raised:
        run(service.enroll(Principal(ADMIN_SUBJECT, frozenset({"admin"})), valid_request()))

    assert raised.value.status_code == status_code
    assert raised.value.code == error_code
    assert identity.created is None


def test_enrollment_rejects_unenrolled_or_non_admin_actor() -> None:
    service = EnrollmentService(
        settings(),
        FakeStore(context_error=enrollment.EnrollmentCallerNotAdmin()),
        FakeIdentityProvider(),
    )

    with pytest.raises(enrollment.ApiError) as raised:
        run(service.enroll(Principal(ADMIN_SUBJECT, frozenset({"admin"})), valid_request()))

    assert raised.value.status_code == 403
    assert raised.value.code == "ERR-014"


def test_keycloak_duplicate_username_returns_conflict() -> None:
    service = EnrollmentService(
        settings(),
        FakeStore(),
        FakeIdentityProvider(create_error=IdentityProviderUserExists()),
    )

    with pytest.raises(enrollment.ApiError) as raised:
        run(service.enroll(Principal(ADMIN_SUBJECT, frozenset({"admin"})), valid_request()))

    assert raised.value.status_code == 409
    assert raised.value.code == "ERR-022"


@pytest.mark.parametrize("role", ["owner", "ADMIN", "", 4])
def test_enrollment_role_is_strictly_limited(role: object) -> None:
    with pytest.raises(ValueError):
        EnrollmentInput(
            identifiant="agent.demo1",
            nom_complet="Agent Démo 1",
            ministere_code="MIN-DEMO-A",
            role=role,
        )


def test_enrollment_rejects_unexpected_fields_without_reflecting_input() -> None:
    with pytest.raises(ValueError):
        EnrollmentInput(
            identifiant="agent.demo1",
            nom_complet="Agent Démo 1",
            ministere_code="MIN-DEMO-A",
            role="agent",
            mot_de_passe="do-not-reflect-this",
        )


def test_database_failure_compensates_keycloak_user() -> None:
    identity = FakeIdentityProvider()
    service = EnrollmentService(
        settings(),
        FakeStore(save_error=enrollment.EnrollmentUnavailable()),
        identity,
    )

    with pytest.raises(enrollment.ApiError) as raised:
        run(service.enroll(Principal(ADMIN_SUBJECT, frozenset({"admin"})), valid_request()))

    assert raised.value.status_code == 503
    assert raised.value.code == "ERR-500"
    assert identity.deleted == [KEYCLOAK_USER_ID]


def test_failed_keycloak_compensation_is_reported() -> None:
    identity = FakeIdentityProvider(
        delete_error=IdentityProviderUnavailable("provider unavailable")
    )
    service = EnrollmentService(
        settings(),
        FakeStore(save_error=enrollment.EnrollmentUnavailable()),
        identity,
    )

    with pytest.raises(enrollment.ApiError) as raised:
        run(service.enroll(Principal(ADMIN_SUBJECT, frozenset({"admin"})), valid_request()))

    assert raised.value.status_code == 503
    assert raised.value.code == "ERR-500"
    assert raised.value.details == {"compensation": "echec"}
    assert identity.deleted == [KEYCLOAK_USER_ID]


def test_http_endpoint_requires_admin_and_returns_enrollment_contract() -> None:
    app: FastAPI = main.create_app(settings())
    store = FakeStore()
    identity = FakeIdentityProvider()
    app.state.enrollment_service = EnrollmentService(settings(), store, identity)
    app.dependency_overrides[require_admin] = lambda: Principal(
        ADMIN_SUBJECT,
        frozenset({"admin"}),
    )

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/agents",
                json={
                    "identifiant": "agent.demo1",
                    "nom_complet": "Agent Démo 1",
                    "ministere_code": "MIN-DEMO-A",
                    "fonction": "Chargé d’études",
                    "role": "agent",
                },
                headers={"X-Request-ID": "b9c9b9e8-78da-44e1-a7ee-3f6861a6f60a"},
            )

    response = run(send())

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == "b9c9b9e8-78da-44e1-a7ee-3f6861a6f60a"
    assert response.json()["request_id"] == "b9c9b9e8-78da-44e1-a7ee-3f6861a6f60a"
    assert response.json()["data"]["mot_de_passe_temporaire"]


def test_http_endpoint_rejects_missing_bearer_token() -> None:
    app: FastAPI = main.create_app(settings())

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/agents", json={})

    response = run(send())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ERR-013"


def test_http_validation_error_uses_safe_error_envelope() -> None:
    app: FastAPI = main.create_app(settings())
    app.dependency_overrides[require_admin] = lambda: Principal(
        ADMIN_SUBJECT,
        frozenset({"admin"}),
    )

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/agents",
                json={
                    "identifiant": "agent.demo1",
                    "nom_complet": "Agent Démo 1",
                    "ministere_code": "MIN-DEMO-A",
                    "role": "agent",
                    "mot_de_passe": "do-not-reflect-this",
                },
                headers={"X-Request-ID": "b9c9b9e8-78da-44e1-a7ee-3f6861a6f60a"},
            )

    response = run(send())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ERR-023"
    assert response.json()["error"]["details"] == {
        "champs": [{"champ": "mot_de_passe", "erreur": "extra_forbidden"}]
    }
    assert "do-not-reflect-this" not in response.text


def test_keycloak_admin_client_sets_temporary_password_and_realm_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assigned_id = uuid4()
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "service-token"})
        if request.method == "POST" and request.url.path.endswith("/users"):
            return httpx.Response(
                201,
                headers={"Location": f"{request.url}/{assigned_id}"},
            )
        if request.method == "PUT" and request.url.path.endswith("/reset-password"):
            return httpx.Response(204)
        if request.method == "GET" and request.url.path.endswith("/roles/agent"):
            return httpx.Response(
                200,
                json={"id": "realm-agent-role-id", "name": "agent"},
            )
        if request.method == "POST" and request.url.path.endswith("/role-mappings/realm"):
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    client = KeycloakAdminClient(settings())

    user_id = run(
        client.create_user(
            "agent.demo1",
            "Agent Démo 1",
            "agent",
            "one-time-password",
        )
    )

    assert user_id == assigned_id
    assert all(request.url.host == "keycloak" for request in requests)
    create_request = next(
        request
        for request in requests
        if request.method == "POST" and request.url.path.endswith("/users")
    )
    assert b"CONFIGURE_TOTP" in create_request.content
    assert b"UPDATE_PASSWORD" in create_request.content
    assert b"oryma_enrollment_id" in create_request.content
    password_request = next(
        request for request in requests if request.url.path.endswith("/reset-password")
    )
    assert b'"temporary":true' in password_request.content
    assert b"one-time-password" in password_request.content
    mapping_request = next(
        request for request in requests if request.url.path.endswith("/role-mappings/realm")
    )
    assert b"realm-agent-role-id" in mapping_request.content


@pytest.mark.parametrize(
    ("delete_status", "expected_error"),
    [(204, IdentityProviderUnavailable), (500, IdentityCompensationFailed)],
)
def test_keycloak_client_compensates_after_role_assignment_failure(
    monkeypatch: pytest.MonkeyPatch,
    delete_status: int,
    expected_error: type[Exception],
) -> None:
    assigned_id = uuid4()
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "service-token"})
        if request.method == "POST" and request.url.path.endswith("/users"):
            return httpx.Response(201, headers={"Location": f"{request.url}/{assigned_id}"})
        if request.method == "PUT" and request.url.path.endswith("/reset-password"):
            return httpx.Response(204)
        if request.method == "GET" and request.url.path.endswith("/roles/agent"):
            return httpx.Response(500)
        if request.method == "DELETE" and request.url.path.endswith(f"/users/{assigned_id}"):
            return httpx.Response(delete_status)
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    client = KeycloakAdminClient(settings())

    with pytest.raises(expected_error):
        run(client.create_user("agent.demo1", "Agent Démo 1", "agent", "one-time-password"))

    assert any(
        request.method == "DELETE" and request.url.path.endswith(f"/users/{assigned_id}")
        for request in requests
    )
