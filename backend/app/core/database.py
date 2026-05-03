from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import get_settings

Base = declarative_base()


class DatabaseManager:
    """Manage the async database engine and session factory."""

    def __init__(self) -> None:
        self.engine = None
        self.async_session_maker = None

    def initialize(self) -> None:
        settings = get_settings()
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def get_session(self):
        if self.async_session_maker is None:
            self.initialize()
        async with self.async_session_maker() as session:
            yield session

    async def create_tables(self) -> None:
        if self.engine is None:
            self.initialize()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if self.engine.dialect.name == "postgresql":
                await conn.execute(
                    text("ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS company_logo TEXT DEFAULT ''")
                )
                await conn.execute(
                    text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS pause_started_at TIMESTAMP WITH TIME ZONE")
                )
                await conn.execute(
                    text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS paused_minutes DOUBLE PRECISION DEFAULT 0.0")
                )
                await conn.execute(
                    text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS session_started_at TIMESTAMP WITH TIME ZONE")
                )
                await conn.execute(
                    text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS accumulated_hours DOUBLE PRECISION DEFAULT 0.0")
                )

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()


db_manager = DatabaseManager()
