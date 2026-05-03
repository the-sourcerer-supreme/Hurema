import asyncio
from pathlib import Path
from urllib.parse import urlparse

import asyncpg


async def main() -> None:
    env_path = Path(__file__).with_name(".env")
    target_dsn = "postgresql://postgres:Hash123@localhost:5432/empay_db"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                target_dsn = line.split("=", 1)[1].strip().replace("postgresql+asyncpg://", "postgresql://")
                break

    parsed = urlparse(target_dsn)
    database_name = parsed.path.lstrip("/") or "empay_db"
    admin_dsn = parsed._replace(path="/postgres").geturl()

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'CREATE DATABASE "{database_name}"')
        print(f"Database {database_name} created successfully.")
    except asyncpg.exceptions.DuplicateDatabaseError:
        print(f"Database {database_name} already exists.")
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
