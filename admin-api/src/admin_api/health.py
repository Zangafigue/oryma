import asyncpg
import httpx


async def check_database(database_url: str | None) -> bool:
    if not database_url:
        return False

    try:
        connection = await asyncpg.connect(database_url, timeout=2)
        try:
            await connection.execute("SELECT 1")
        finally:
            await connection.close()
    except (asyncpg.PostgresError, OSError, TimeoutError, ValueError):
        return False

    return True


async def check_http_endpoint(url: str | None) -> bool:
    if not url:
        return False

    try:
        async with httpx.AsyncClient(timeout=2, follow_redirects=False) as client:
            response = await client.get(url)
    except (httpx.HTTPError, ValueError):
        return False

    return 200 <= response.status_code < 300
