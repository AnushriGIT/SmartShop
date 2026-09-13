"""End-to-end tests for `run_full_pipeline()` against a live PostgreSQL
instance (started via `docker compose up -d postgres`). See
`tests/conftest.py` for the fixtures that skip these automatically when
PostgreSQL isn't reachable.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.pipeline.orchestrator import run_full_pipeline
from app.pipeline.persistence import ProductRecord, ReviewRecord, StorePolicyRecord

pytestmark = pytest.mark.integration


def _write_valid_dataset(data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "products.csv").write_text(
        "id,name,brand,category,price,description,stock,rating\n"
        "SP0001,Widget Pro,TechBrand,electronics,19.99,Premium widget device,100,4.5\n",
        encoding="utf-8",
    )
    (data_root / "reviews.csv").write_text(
        "product_id,rating,text,date\n"
        "SP0001,4.5,Great product!,2026-09-10\n",
        encoding="utf-8",
    )
    (data_root / "store_policies.csv").write_text(
        "policy_type,description,conditions,timeframe\n"
        "returns,30-day returns,Keep packaging | Resale condition,30\n",
        encoding="utf-8",
    )


async def _table_counts(db_session_factory) -> tuple[int, int, int]:
    async with db_session_factory() as session:
        products = (
            await session.execute(select(func.count()).select_from(ProductRecord))
        ).scalar_one()
        reviews = (
            await session.execute(select(func.count()).select_from(ReviewRecord))
        ).scalar_one()
        policies = (
            await session.execute(select(func.count()).select_from(StorePolicyRecord))
        ).scalar_one()
    return products, reviews, policies


async def test_run_full_pipeline_persists_real_source_data(db_session_factory):
    report = await run_full_pipeline()

    assert report.status == "success"
    assert report.rows_persisted == {"products": 2000, "reviews": 4000, "policies": 22}
    assert report.batch_count > 0
    assert report.retries == 0
    assert report.persistence_latency_seconds >= 0

    assert await _table_counts(db_session_factory) == (2000, 4000, 22)


async def test_run_full_pipeline_rerun_is_idempotent(db_session_factory):
    first = await run_full_pipeline()
    second = await run_full_pipeline()

    assert first.status == "success"
    assert second.status == "success"
    assert second.rows_persisted == first.rows_persisted
    assert await _table_counts(db_session_factory) == (2000, 4000, 22)


async def test_run_full_pipeline_validation_failure_leaves_database_untouched(
    db_session_factory, tmp_path: Path
):
    data_root = tmp_path / "data"
    data_root.mkdir()
    # One malformed product row (non-numeric price) with a zero invalid-row
    # threshold: validation must fail before persistence ever starts.
    (data_root / "products.csv").write_text(
        "id,name,brand,category,price,description,stock,rating\n"
        "bad,Phone,TechCo,smartphone,not-a-price,Phone,1,4.0\n",
        encoding="utf-8",
    )
    (data_root / "reviews.csv").write_text(
        "product_id,rating,text,date\n",
        encoding="utf-8",
    )
    (data_root / "store_policies.csv").write_text(
        "policy_type,description,conditions,timeframe\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="threshold exceeded") as excinfo:
        await run_full_pipeline(data_root=data_root)

    assert excinfo.value.pipeline_report.status == "failed"
    assert await _table_counts(db_session_factory) == (0, 0, 0)


async def test_run_full_pipeline_does_not_dispose_an_injected_engine(
    db_engine, clean_schema, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    data_root = tmp_path / "data"
    _write_valid_dataset(data_root)

    # AsyncEngine.dispose is not assignable on the instance, so patch the
    # class for the duration of this test (monkeypatch auto-reverts it).
    dispose_calls = {"count": 0}
    original_dispose = AsyncEngine.dispose

    async def tracking_dispose(self, *args, **kwargs):
        dispose_calls["count"] += 1
        await original_dispose(self, *args, **kwargs)

    monkeypatch.setattr(AsyncEngine, "dispose", tracking_dispose)

    report = await run_full_pipeline(data_root=data_root, engine=db_engine)

    assert report.status == "success"
    assert dispose_calls["count"] == 0
