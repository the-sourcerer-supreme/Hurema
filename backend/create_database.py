import asyncio
import asyncpg


async def main() -> None:
    dsn = "postgresql://postgres:Neeraj%401907@localhost:5432/postgres"
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute('CREATE DATABASE odoo_hackathon')
        print('Database odoo_hackathon created successfully.')
    except asyncpg.exceptions.DuplicateDatabaseError:
        print('Database odoo_hackathon already exists.')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
