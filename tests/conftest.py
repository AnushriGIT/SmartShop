"""Shared fixtures for the Smartshop pipeline test suite."""

from __future__ import annotations

import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path

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

# Same env-var-override-with-default idiom as app/main.py's REPORT_ROOT_ENV.
TEST_REPORT_ROOT_ENV = "SMARTSHOP_TEST_REPORT_ROOT"
DEFAULT_TEST_REPORT_ROOT = "reports/test-results"


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Write a small durable JSON results file after every pytest run (Rule 4).

    Root-level, so this fires for *any* invocation — the fast suite, an
    `integration` run, the real-API `eval` suite, or a mix — not just eval.
    Writes both a timestamped file (history) and ``latest.json`` (quick
    access) under ``reports/test-results/`` (already-gitignored, same
    convention as the pipeline's run reports in ``app/main.py``), including
    the actual CLI args pytest was invoked with, so a reviewer can tell which
    subset of the suite a given results file covers without guessing.
    """

    reports = [
        report
        for outcome in ("passed", "failed", "skipped")
        for report in terminalreporter.stats.get(outcome, [])
        if report.when == "call"
    ]
    if not reports:
        return

    results = []
    for report in reports:
        entry: dict[str, str] = {"test": report.nodeid, "outcome": report.outcome}
        if report.outcome != "passed":
            try:
                entry["detail"] = str(report.longrepr.reprcrash.message)
            except AttributeError:
                entry["detail"] = str(report.longrepr)
        results.append(entry)

    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "pytest_args": list(terminalreporter.config.invocation_params.args),
        "total": len(results),
        "passed": sum(1 for r in results if r["outcome"] == "passed"),
        "failed": sum(1 for r in results if r["outcome"] == "failed"),
        "skipped": sum(1 for r in results if r["outcome"] == "skipped"),
        "results": results,
    }

    report_root = Path(os.getenv(TEST_REPORT_ROOT_ENV, DEFAULT_TEST_REPORT_ROOT))
    report_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (report_root / f"{run_id}.json").write_text(json.dumps(payload, indent=2))
    (report_root / "latest.json").write_text(json.dumps(payload, indent=2))


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
