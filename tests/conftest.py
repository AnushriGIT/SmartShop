"""Shared fixtures for the Smartshop pipeline test suite."""

from __future__ import annotations

import os
import socket

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.pipeline.persistence import (
    Base,
    DATABASE_URL_ENV,
    DEFAULT_DATABASE_URL,
    create_engine,
    create_session_factory,
)


def _postgres_reachable(url: str) -> bool:
    """Cheap TCP probe so DB-dependent tests skip cleanly instead of hanging."""

    parsed = make_url(url)
    try:
        with socket.create_connection((parsed.host, parsed.port or 5432), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def database_url() -> str:
    """Resolve the integration-test database URL the same way persistence.py does."""

    return os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)


@pytest.fixture(scope="session")
def postgres_available(database_url: str) -> bool:
    return _postgres_reachable(database_url)


@pytest_asyncio.fixture
async def db_engine(database_url: str, postgres_available: bool) -> AsyncEngine:
    # Skipping (rather than failing) keeps `pytest -q` usable on a machine
    # without `docker compose up -d postgres` running; only tests marked
    # `integration` depend on this fixture.
    if not postgres_available:
        pytest.skip("PostgreSQL not reachable; run `docker compose up -d postgres` first.")

    engine = create_engine(database_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def clean_schema(db_engine: AsyncEngine):
    """Drop-and-recreate all tables so each test starts from an empty schema."""

    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session_factory(
    db_engine: AsyncEngine, clean_schema: None
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(db_engine)
