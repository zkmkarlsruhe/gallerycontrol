# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Database connection and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gallerycontrol.config import get_config


class DatabaseManager:
    """Manage database connections and sessions."""

    def __init__(self):
        self.engine = None
        self.session_factory = None

    def initialize(self) -> None:
        """Initialize database engine and session factory."""
        config = get_config()
        database_url = config.get("database.url")

        # Validate database URL - only PostgreSQL is supported
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Must be a PostgreSQL connection string (postgresql+asyncpg://...)"
            )
        if "sqlite" in database_url.lower():
            raise ValueError(
                "SQLite is not supported. Use PostgreSQL instead. "
                "Set DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname"
            )
        if not database_url.startswith("postgresql"):
            raise ValueError(
                f"Invalid database URL: {database_url[:30]}... "
                "Must be a PostgreSQL connection string (postgresql+asyncpg://...)"
            )

        pool_size = config.get("database.pool_size", 20)
        pool_pre_ping = config.get("database.pool_pre_ping", True)
        echo = config.get("database.echo", False)

        self.engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            pool_pre_ping=pool_pre_ping,
            echo=echo,
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global database manager
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session."""
    db = get_db_manager()
    async with db.session() as session:
        yield session
