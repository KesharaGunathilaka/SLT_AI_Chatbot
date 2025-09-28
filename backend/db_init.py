import asyncio
import os
from urllib.parse import urlparse
import asyncpg
from db import create_pool, create_tables

DATABASE_URL = os.getenv("DATABASE_URL")


async def ensure_database():
    url = urlparse(DATABASE_URL)
    db_name = url.path.lstrip("/")
    user = url.username
    password = url.password
    host = url.hostname
    port = url.port or 5432

    conn = await asyncpg.connect(
        user=user, password=password, host=host, port=port, database="postgres"
    )

    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", db_name)
    if not exists:
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Database {db_name} created.")
    else:
        print(f"Database {db_name} already exists.")
    await conn.close()


async def run():

    await ensure_database()

    pool = await create_pool()

    await create_tables(pool)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
