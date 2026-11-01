import asyncio
import os
from pathlib import Path

import asyncpg

MIGRATIONS_DIRECTORY = Path(__file__).parent / "sql_migrations"
MIGRATION_LOCK_ID = 734_201_106


async def apply_migrations(database_url: str) -> None:
    connection = await asyncpg.connect(database_url)
    lock_acquired = False
    try:
        await connection.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_ID)
        lock_acquired = True
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        for migration_path in sorted(MIGRATIONS_DIRECTORY.glob("[0-9][0-9][0-9]_*.sql")):
            version = migration_path.name
            already_applied = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = $1)",
                version,
            )
            if already_applied:
                continue

            async with connection.transaction():
                await connection.execute(migration_path.read_text(encoding="utf-8"))
                await connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version,
                )
    finally:
        try:
            if lock_acquired:
                await connection.execute("SELECT pg_advisory_unlock($1)", MIGRATION_LOCK_ID)
        finally:
            await connection.close()


def main() -> None:
    database_url = os.getenv("ADMINAPI_DATABASE_URL")
    if not database_url:
        raise SystemExit("ADMINAPI_DATABASE_URL doit être défini pour appliquer les migrations.")

    asyncio.run(apply_migrations(database_url))
