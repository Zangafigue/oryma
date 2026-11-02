import asyncio
from uuid import UUID

import httpx
import pytest

from admin_api import enrollment, main, revocation
from admin_api.auth import Principal, require_admin
from admin_api.config import Settings
from admin_api.enrollment import IdentityProviderUnavailable, KeycloakAdminClient
from admin_api.revocation import (
    RevocationAgentNotFound,
    RevocationAlreadyRunning,
    RevocationCallerNotAdmin,
    RevocationResult,
    RevocationRun,
    RevocationService,
    RevocationTarget,
    RevocationUnavailable,
    SynapseAdminClient,
    SynapseAdminUnavailable,
)

ADMIN_KEYCLOAK_ID = UUID("00000000-0000-0000-0000-000000000004")
AGENT_ID = UUID("00000000-0000-0000-0000-000000000010")
AGENT_KEYCLOAK_ID = UUID("00000000-0000-0000-0000-000000000011")
MATRIX_ID = "@agent.demo1:oryma.local"


def run(awaitable):
    return asyncio.run(awaitable)


def settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql://test",
        "keycloak_healthcheck_url": None,
        "synapse_healthcheck_url": None,
        "oidc_issuer": "https://oryma.local/auth/realms/oryma",
        "oidc_jwks_url": "http://keycloak:8080/auth/realms/oryma/protocol/openid-connect/certs",
        "keycloak_admin_client_secret": "test-only",
        "synapse_admin_access_token": "test-only-synapse-token",
    }
    values.update(overrides)
    return Settings(**values)


class FakeStore:
    def __init__(
        self,
        *,
        failure: Exception | None = None,
        legacy_already_revoked: bool = False,
        mark_failure_order: int | None = None,
    ) -> None:
        self.failure = failure
        self.legacy_already_revoked = legacy_already_revoked
        self.mark_failure_order = mark_failure_order
        self.completed: set[int] = set()
        self.execute_calls = 0

    async def execute(self, caller_keycloak_id, agent_id, handler) -> RevocationResult:
        self.execute_calls += 1
        if self.failure:
            raise self.failure

        async def mark_step_completed(order: int) -> None:
            if order == self.mark_failure_order:
                raise RevocationUnavailable
            self.completed.add(order)

        return await handler(
            RevocationRun(
                target=RevocationTarget(AGENT_ID, AGENT_KEYCLOAK_ID, MATRIX_ID),
                actor_id=ADMIN_KEYCLOAK_ID,
                completed_steps=frozenset(self.completed),
                legacy_already_revoked=self.legacy_already_revoked,
                mark_step_completed=mark_step_completed,
            )
        )


class FakeKeycloak:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.disable_error: Exception | None = None

    async def disable_user(self, keycloak_id: UUID) -> None:
        self.calls.append("keycloak_disable")
        if self.disable_error:
            raise self.disable_error

    async def logout_user_sessions(self, keycloak_id: UUID) -> None:
        self.calls.append("keycloak_logout")


class FakeSynapse:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.delete_failures = 0

    async def delete_all_devices(self, matrix_id: str) -> None:
        self.calls.append("synapse_devices")
        if self.delete_failures:
            self.delete_failures -= 1
            raise SynapseAdminUnavailable

    async def deactivate_user(self, matrix_id: str) -> None:
        self.calls.append("synapse_deactivate")


def make_service(store=None, keycloak=None, synapse=None):
    return RevocationService(
        settings(),
        store or FakeStore(),
        keycloak or FakeKeycloak(),
        synapse or FakeSynapse(),
    )


def test_revocation_runs_all_six_steps_in_contract_order() -> None:
    store = FakeStore()
    keycloak = FakeKeycloak()
    synapse = FakeSynapse()

    result = run(
        make_service(store, keycloak, synapse).revoke(
            Principal(str(ADMIN_KEYCLOAK_ID), frozenset({"admin"})),
            AGENT_ID,
        )
    )

    assert result["statut_operation"] == "complete"
    assert [step["ordre"] for step in result["etapes"]] == list(range(1, 7))
    assert keycloak.calls == ["keycloak_disable", "keycloak_logout"]
    assert synapse.calls == ["synapse_devices", "synapse_deactivate"]
    assert store.completed == set(range(1, 7))


def test_retry_resumes_after_failed_synapse_step_without_repeating_successes() -> None:
    store = FakeStore()
    keycloak = FakeKeycloak()
    synapse = FakeSynapse()
    synapse.delete_failures = 1
    service = make_service(store, keycloak, synapse)
    principal = Principal(str(ADMIN_KEYCLOAK_ID), frozenset({"admin"}))

    with pytest.raises(revocation.ApiError) as first:
        run(service.revoke(principal, AGENT_ID))
    assert first.value.status_code == 502
    assert first.value.details["etapes"][2]["statut"] == "echec"
    assert first.value.details["etapes"][3]["statut"] == "ignoree"

    result = run(service.revoke(principal, AGENT_ID))

    assert result["statut_operation"] == "complete"
    assert keycloak.calls == ["keycloak_disable", "keycloak_logout"]
    assert synapse.calls == ["synapse_devices", "synapse_devices", "synapse_deactivate"]
    assert store.completed == set(range(1, 7))


def test_already_revoked_legacy_agent_is_idempotent() -> None:
    keycloak = FakeKeycloak()
    synapse = FakeSynapse()
    result = run(
        make_service(
            FakeStore(legacy_already_revoked=True),
            keycloak,
            synapse,
        ).revoke(Principal(str(ADMIN_KEYCLOAK_ID), frozenset({"admin"})), AGENT_ID)
    )

    assert result["statut_operation"] == "complete"
    assert all(step["statut"] == "reussie" for step in result["etapes"])
    assert keycloak.calls == []
    assert synapse.calls == []


@pytest.mark.parametrize(
    ("failure", "status_code", "error_code"),
    [
        (RevocationCallerNotAdmin(), 403, "ERR-014"),
        (RevocationAgentNotFound(), 404, "ERR-031"),
        (RevocationAlreadyRunning(), 409, "ERR-034"),
        (RevocationUnavailable(), 503, "ERR-500"),
    ],
)
def test_store_errors_map_to_api_contract(
    failure: Exception,
    status_code: int,
    error_code: str,
) -> None:
    service = make_service(FakeStore(failure=failure))

    with pytest.raises(revocation.ApiError) as raised:
        run(
            service.revoke(
                Principal(str(ADMIN_KEYCLOAK_ID), frozenset({"admin"})),
                AGENT_ID,
            )
        )

    assert raised.value.status_code == status_code
    assert raised.value.code == error_code


def test_persistence_failure_returns_incomplete_and_retries_unrecorded_step() -> None:
    store = FakeStore(mark_failure_order=1)
    keycloak = FakeKeycloak()
    service = make_service(store, keycloak)
    principal = Principal(str(ADMIN_KEYCLOAK_ID), frozenset({"admin"}))

    with pytest.raises(revocation.ApiError) as raised:
        run(service.revoke(principal, AGENT_ID))

    assert raised.value.details["etapes"][0]["detail"] == "persistance_indisponible"
    assert keycloak.calls == ["keycloak_disable"]


def test_synapse_admin_client_calls_device_and_deactivation_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/devices"):
            return httpx.Response(200, json={"devices": [{"device_id": "phone-1"}]})
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        if request.method == "GET":
            return httpx.Response(200, json={"deactivated": False})
        if request.method == "POST":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(revocation.httpx, "AsyncClient", mock_client)
    client = SynapseAdminClient(settings())
    run(client.delete_all_devices(MATRIX_ID))
    run(client.deactivate_user(MATRIX_ID))

    assert [request.method for request in requests] == ["GET", "DELETE", "GET", "POST"]
    assert requests[0].url.path.endswith("/devices")
    assert requests[1].url.path.endswith("/devices/phone-1")
    assert requests[3].content == b'{"erase":false}'
    assert requests[0].headers["Authorization"] == "Bearer test-only-synapse-token"


def test_synapse_admin_client_treats_missing_devices_as_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"errcode": "M_NOT_FOUND"})

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(revocation.httpx, "AsyncClient", mock_client)
    run(SynapseAdminClient(settings()).delete_all_devices(MATRIX_ID))


def test_synapse_admin_client_treats_deactivated_user_as_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"deactivated": True})

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(revocation.httpx, "AsyncClient", mock_client)
    run(SynapseAdminClient(settings()).deactivate_user(MATRIX_ID))

    assert len(requests) == 1
    assert requests[0].method == "GET"


def test_synapse_admin_client_requires_token() -> None:
    with pytest.raises(SynapseAdminUnavailable):
        run(
            SynapseAdminClient(settings(synapse_admin_access_token=None)).delete_all_devices(
                MATRIX_ID
            )
        )


def test_keycloak_revocation_uses_expected_admin_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "keycloak-service-token"})
        return httpx.Response(204)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    client = KeycloakAdminClient(settings())
    run(client.disable_user(AGENT_KEYCLOAK_ID))
    run(client.logout_user_sessions(AGENT_KEYCLOAK_ID))

    admin_requests = [
        request
        for request in requests
        if not request.url.path.endswith("/protocol/openid-connect/token")
    ]
    assert [request.method for request in admin_requests] == ["PUT", "POST"]
    assert admin_requests[0].url.path.endswith(f"/users/{AGENT_KEYCLOAK_ID}")
    assert admin_requests[0].content == b'{"enabled":false}'
    assert admin_requests[1].url.path.endswith(f"/users/{AGENT_KEYCLOAK_ID}/logout")


def test_keycloak_revocation_reports_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return httpx.Response(200, json={"access_token": "keycloak-service-token"})
        return httpx.Response(500)

    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(enrollment.httpx, "AsyncClient", mock_client)
    with pytest.raises(IdentityProviderUnavailable):
        run(KeycloakAdminClient(settings()).disable_user(AGENT_KEYCLOAK_ID))


def test_revoke_http_route_returns_contract_envelope() -> None:
    app = main.create_app(settings())
    app.state.revocation_service = make_service()
    app.dependency_overrides[require_admin] = lambda: Principal(
        str(ADMIN_KEYCLOAK_ID),
        frozenset({"admin"}),
    )

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(f"/api/v1/agents/{AGENT_ID}/revoke")

    response = run(send())

    assert response.status_code == 200
    assert response.json()["data"]["statut_operation"] == "complete"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
