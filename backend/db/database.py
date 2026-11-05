"""SQLModel engine + session management (async).

Status: COMPLETE (Phase 6).
SQLite (aiosqlite) for dev, PostgreSQL (prod) via DATABASE_URL.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel


class Database:
    """Async database facade over SQLModel metadata."""

    def __init__(self, url: str) -> None:
        self._engine = create_async_engine(url)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        """Underlying SQLAlchemy async engine."""
        return self._engine

    async def create_all(self) -> None:
        """Create all registered tables."""
        async with self._engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    async def dispose(self) -> None:
        """Dispose of the engine's connection pool."""
        await self._engine.dispose()

    def session(self) -> AsyncSession:
        """Create a new async session."""
        return self._session_factory()
