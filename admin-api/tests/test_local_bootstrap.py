import asyncio
import sys
from contextlib import asynccontextmanager
from uuid import UUID

import pytest

from admin_api import local_bootstrap

KEYCLOAK_ID = UUID("b1a75cc4-9c44-4c06-a63e-2475d2af47df")
AGENT_ID = UUID("2388cad0-27e8-47d1-9af7-4a13542ed66a")
MATRIX_ID = "@admin:oryma.local"
ADMIN_NAME = "Administrateur de démonstration"


class FakeConnection:
    def __init__(self) -> None:
        self.admin: dict[str, object] | None = None
        self.ministry_name: str | None = None
        self.audit_entries: list[tuple[object, ...]] = []
        self.closed = False

    @asynccontextmanager
    async def transaction(self):
        yield

    async def execute(self, query: str, *args: object) -> str:
        if "BOOTSTRAP_ADMIN_LOCAL" in query:
            self.audit_entries.append(args)
        return "OK"

    async def fetchrow(self, query: str, *args: object) -> dict[str, object] | None:
        if "WHERE a.keycloak_id = $1" in query and self.admin:
            return self.admin
        return None

    async def fetchval(self, query: str, *args: object) -> object:
        if "matrix_id = $1" in query:
            return False
        if "role = 'admin'" in query:
            return self.admin is not None
        if "SELECT id FROM ministeres" in query:
            return 1 if self.ministry_name is not None else None
        if "SELECT nom FROM ministeres" in query:
            return self.ministry_name
        if "INSERT INTO ministeres" in query:
            self.ministry_name = str(args[1])
            return 1
        if "INSERT INTO agents" in query:
            self.admin = {
                "keycloak_id": args[0],
                "matrix_id": args[1],
                "nom_complet": args[2],
                "role": "admin",
                "statut": "actif",
                "ministere_code": local_bootstrap.MINISTRY_CODE,
                "ministere_nom": local_bootstrap.MINISTRY_NAME,
            }
            return AGENT_ID
        raise AssertionError(f"Unexpected query: {query}")

    async def close(self) -> None:
        self.closed = True


def test_local_bootstrap_creates_ministry_admin_and_audit(monkeypatch) -> None:
    connection = FakeConnection()

    async def connect(_database_url: str) -> FakeConnection:
        return connection

    monkeypatch.setattr(local_bootstrap.asyncpg, "connect", connect)

    created = asyncio.run(
        local_bootstrap.bootstrap_local_admin(
            "postgresql://test",
            KEYCLOAK_ID,
            MATRIX_ID,
            ADMIN_NAME,
        )
    )

    assert created is True
    assert connection.ministry_name == local_bootstrap.MINISTRY_NAME
    assert connection.admin is not None
    assert connection.admin["keycloak_id"] == KEYCLOAK_ID
    assert connection.audit_entries
    assert connection.closed is True


def test_local_bootstrap_is_idempotent_for_the_same_active_admin(monkeypatch) -> None:
    connection = FakeConnection()
    connection.admin = {
        "keycloak_id": KEYCLOAK_ID,
        "matrix_id": MATRIX_ID,
        "nom_complet": ADMIN_NAME,
        "role": "admin",
        "statut": "actif",
        "ministere_code": local_bootstrap.MINISTRY_CODE,
        "ministere_nom": local_bootstrap.MINISTRY_NAME,
    }

    async def connect(_database_url: str) -> FakeConnection:
        return connection

    monkeypatch.setattr(local_bootstrap.asyncpg, "connect", connect)

    created = asyncio.run(
        local_bootstrap.bootstrap_local_admin(
            "postgresql://test",
            KEYCLOAK_ID,
            MATRIX_ID,
            ADMIN_NAME,
        )
    )

    assert created is False
    assert connection.audit_entries == []
    assert connection.closed is True


def test_local_bootstrap_refuses_without_local_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("ORYMA_ENVIRONMENT", "development")
    monkeypatch.delenv("ORYMA_ENABLE_LOCAL_BOOTSTRAP", raising=False)
    monkeypatch.setenv("ADMINAPI_DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "admin-api-bootstrap-local",
            "--confirm-local",
            "--keycloak-id",
            str(KEYCLOAK_ID),
            "--matrix-id",
            MATRIX_ID,
            "--admin-name",
            ADMIN_NAME,
        ],
    )

    with pytest.raises(SystemExit, match="Bootstrap refusé"):
        local_bootstrap.main()


def test_local_bootstrap_refuses_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("ORYMA_ENVIRONMENT", "production")
    monkeypatch.setenv("ORYMA_ENABLE_LOCAL_BOOTSTRAP", "true")
    monkeypatch.setenv("ADMINAPI_DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "admin-api-bootstrap-local",
            "--confirm-local",
            "--keycloak-id",
            str(KEYCLOAK_ID),
            "--matrix-id",
            MATRIX_ID,
            "--admin-name",
            ADMIN_NAME,
        ],
    )

    with pytest.raises(SystemExit, match="ORYMA_ENVIRONMENT"):
        local_bootstrap.main()
