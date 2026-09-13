"""Streaming CSV ingestion with exact-header and row metadata checks."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.pipeline.paths import resolve_source_path

PRODUCT_HEADERS = (
    "id",
    "name",
    "brand",
    "category",
    "price",
    "description",
    "stock",
    "rating",
)
REVIEW_HEADERS = ("product_id", "rating", "text", "date")
POLICY_HEADERS = ("policy_type", "description", "conditions", "timeframe")


class IngestionError(ValueError):
    """Raised when a source file cannot satisfy its structural contract."""


@dataclass(frozen=True)
class SourceRow:
    """A raw CSV row with enough provenance for validation/quarantine."""

    source_path: Path
    row_number: int
    values: dict[str, str]


def iter_csv_rows(
    source_name: str | Path,
    expected_headers: tuple[str, ...],
    data_root: str | Path | None = None,
) -> Iterator[SourceRow]:
    """Yield UTF-8 CSV rows after validating the exact header contract."""

    # Path validation happens before opening the file so malformed
    # configuration fails before any source data is consumed.
    source_path = resolve_source_path(source_name, data_root)
    with source_path.open("r", encoding="utf-8", newline="") as source_file:
        reader = csv.DictReader(source_file)
        actual_headers = tuple(reader.fieldnames or ())
        # Header equality is intentionally strict: silently accepting renamed,
        # missing, or reordered fields would corrupt downstream normalization.
        if actual_headers != expected_headers:
            raise IngestionError(
                f"Unexpected headers for {source_path.name}: "
                f"expected {expected_headers}, got {actual_headers}"
            )

        for row_number, row in enumerate(reader, start=2):
            # DictReader stores overflow values under a None key; reject them
            # while the original file and row number are still available.
            if None in row:
                raise IngestionError(
                    f"Malformed row {row_number} in {source_path.name}: "
                    "more values than headers"
                )
            yield SourceRow(
                source_path=source_path,
                row_number=row_number,
                values={header: value for header, value in row.items()},
            )
