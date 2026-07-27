#!/usr/bin/env python3
"""Inspect and load UCI dataset 350 without repairing or reinterpreting values.

The source workbook is an immutable input. This module validates its pinned
hash and two-row header, rejects any non-integral or missing data cell, and
uses insert-only PostgreSQL loading. A repeated load of the same file inserts
zero rows after verifying that every existing raw row matches the source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE_PATH = REPOSITORY_ROOT / "data/raw/default+of+credit+card+clients.zip"
DEFAULT_WORKBOOK_PATH = REPOSITORY_ROOT / "data/raw/default of credit card clients.xls"
DEFAULT_DDL_PATH = REPOSITORY_ROOT / "sql/ingestion/001_raw_credit_card_client.sql"
DEFAULT_LOG_DIRECTORY = REPOSITORY_ROOT / "logs/ingestion"

SOURCE_ID = "uci_default_credit_card_clients"
DATASET_ID = 350
SHEET_NAME = "Data"
PROVIDER = "UCI Machine Learning Repository"
LANDING_PAGE_URL = "https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients"
DOWNLOAD_URL = (
    "https://archive.ics.uci.edu/static/public/350/default%2Bof%2Bcredit%2Bcard%2Bclients.zip"
)
DOI = "10.24432/C55S3H"
LICENSE = "CC BY 4.0"
EXPECTED_ARCHIVE_MEMBER = "default of credit card clients.xls"
EXPECTED_PHYSICAL_ROWS = 30_002
EXPECTED_DATA_ROWS = 30_000
EXPECTED_COLUMNS = 25
POSTGRES_INTEGER_MIN = -(2**31)
POSTGRES_INTEGER_MAX = 2**31 - 1
EXPECTED_ARCHIVE_SHA256 = "56c885f84457f6680f8438f02bfcdac9579323d8a94465ee5f26e32baa727602"
EXPECTED_WORKBOOK_SHA256 = "30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933"

SOURCE_VARIABLE_HEADER = (
    "",
    "X1",
    "X2",
    "X3",
    "X4",
    "X5",
    "X6",
    "X7",
    "X8",
    "X9",
    "X10",
    "X11",
    "X12",
    "X13",
    "X14",
    "X15",
    "X16",
    "X17",
    "X18",
    "X19",
    "X20",
    "X21",
    "X22",
    "X23",
    "Y",
)
SOURCE_FIELD_HEADER = (
    "ID",
    "LIMIT_BAL",
    "SEX",
    "EDUCATION",
    "MARRIAGE",
    "AGE",
    "PAY_0",
    "PAY_2",
    "PAY_3",
    "PAY_4",
    "PAY_5",
    "PAY_6",
    "BILL_AMT1",
    "BILL_AMT2",
    "BILL_AMT3",
    "BILL_AMT4",
    "BILL_AMT5",
    "BILL_AMT6",
    "PAY_AMT1",
    "PAY_AMT2",
    "PAY_AMT3",
    "PAY_AMT4",
    "PAY_AMT5",
    "PAY_AMT6",
    "default payment next month",
)
DATABASE_COLUMNS = (
    "id",
    "limit_bal",
    "sex",
    "education",
    "marriage",
    "age",
    "pay_0",
    "pay_2",
    "pay_3",
    "pay_4",
    "pay_5",
    "pay_6",
    "bill_amt1",
    "bill_amt2",
    "bill_amt3",
    "bill_amt4",
    "bill_amt5",
    "bill_amt6",
    "pay_amt1",
    "pay_amt2",
    "pay_amt3",
    "pay_amt4",
    "pay_amt5",
    "pay_amt6",
    "default_payment_next_month",
)


class SourceIntegrityError(RuntimeError):
    """Raised when the source cannot be proven to match the approved artifact."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}


class RawConflictError(RuntimeError):
    """Raised when an existing raw row differs from the immutable source row."""


@dataclass(frozen=True)
class RejectedCell:
    """One source cell that could not be represented losslessly as an integer."""

    source_row_number: int
    source_column_number: int
    source_field: str
    reason: str
    raw_value: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_row_number": self.source_row_number,
            "source_column_number": self.source_column_number,
            "source_field": self.source_field,
            "reason": self.reason,
            "raw_value": self.raw_value,
        }


@dataclass(frozen=True)
class WorkbookInspection:
    """Validated workbook metadata plus rows ready for insert-only loading."""

    archive_path: Path
    archive_bytes: int
    archive_sha256: str
    archive_member: str
    archive_member_bytes: int
    archive_member_crc32: str
    workbook_path: Path
    workbook_bytes: int
    workbook_sha256: str
    sheet_names: tuple[str, ...]
    sheet_name: str
    physical_rows: int
    data_rows: int
    columns: int
    variable_header: tuple[str, ...]
    field_header: tuple[str, ...]
    parsed_rows: tuple[tuple[int, ...], ...]
    rejected_cells: tuple[RejectedCell, ...]

    def log_summary(self) -> dict[str, Any]:
        rejected_rows = {item.source_row_number for item in self.rejected_cells}
        return {
            "source_id": SOURCE_ID,
            "dataset_id": DATASET_ID,
            "provider": PROVIDER,
            "landing_page_url": LANDING_PAGE_URL,
            "download_url": DOWNLOAD_URL,
            "doi": DOI,
            "license": LICENSE,
            "archive": {
                "path": repository_relative(self.archive_path),
                "bytes": self.archive_bytes,
                "sha256": self.archive_sha256,
                "member": self.archive_member,
                "member_bytes": self.archive_member_bytes,
                "member_crc32": self.archive_member_crc32,
            },
            "workbook": {
                "path": repository_relative(self.workbook_path),
                "bytes": self.workbook_bytes,
                "sha256": self.workbook_sha256,
                "sheet_names": list(self.sheet_names),
                "selected_sheet": self.sheet_name,
                "physical_rows_including_headers": self.physical_rows,
                "data_rows": self.data_rows,
                "columns": self.columns,
                "header_rows": 2,
                "source_variable_header": list(self.variable_header),
                "source_field_header": list(self.field_header),
                "database_columns": list(DATABASE_COLUMNS),
                "cell_storage": "Excel numeric cells; every accepted value is integral",
            },
            "reconciliation": {
                "source_data_rows": self.data_rows,
                "parsed_rows": len(self.parsed_rows),
                "rejected_rows": len(rejected_rows),
                "rejected_cells": len(self.rejected_cells),
            },
            "rejected_cells": [item.as_dict() for item in self.rejected_cells],
        }


def repository_relative(path: Path) -> str:
    """Return a stable repository-relative path where possible."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 without changing the file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SourceIntegrityError(f"{label} not found: {path}")


def _inspect_archive(archive_path: Path, workbook_sha256: str) -> dict[str, Any]:
    _require_file(archive_path, "official archive")
    archive_sha256 = sha256_file(archive_path)
    if archive_sha256 != EXPECTED_ARCHIVE_SHA256:
        raise SourceIntegrityError(
            "archive SHA-256 mismatch: "
            f"expected {EXPECTED_ARCHIVE_SHA256}, observed {archive_sha256}"
        )

    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if names != [EXPECTED_ARCHIVE_MEMBER]:
            raise SourceIntegrityError(
                f"unexpected archive members: expected {[EXPECTED_ARCHIVE_MEMBER]!r}, "
                f"observed {names!r}"
            )
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise SourceIntegrityError(f"archive CRC check failed for {corrupt_member}")
        member = members[0]
        member_digest = hashlib.sha256()
        with archive.open(member, "r") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                member_digest.update(block)
        if member_digest.hexdigest() != workbook_sha256:
            raise SourceIntegrityError(
                "archive member differs from extracted workbook: "
                f"member SHA-256 {member_digest.hexdigest()}, workbook SHA-256 "
                f"{workbook_sha256}"
            )

    return {
        "bytes": archive_path.stat().st_size,
        "sha256": archive_sha256,
        "member": member.filename,
        "member_bytes": member.file_size,
        "member_crc32": f"{member.CRC:08x}",
    }


def _require_xlrd() -> Any:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "The official source is an Excel .xls file. Install xlrd>=2.0 "
            "in the project environment before running this loader."
        ) from exc
    return xlrd


def _normalize_header(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple("" if value in ("", None) else str(value) for value in values)


def inspect_source(
    archive_path: Path = DEFAULT_ARCHIVE_PATH,
    workbook_path: Path = DEFAULT_WORKBOOK_PATH,
) -> WorkbookInspection:
    """Validate official files and return rows without imputing or recoding."""

    _require_file(workbook_path, "official workbook")
    workbook_bytes = workbook_path.stat().st_size
    workbook_sha256 = sha256_file(workbook_path)
    if workbook_sha256 != EXPECTED_WORKBOOK_SHA256:
        raise SourceIntegrityError(
            "workbook SHA-256 mismatch: "
            f"expected {EXPECTED_WORKBOOK_SHA256}, observed {workbook_sha256}"
        )
    archive = _inspect_archive(archive_path, workbook_sha256)

    xlrd = _require_xlrd()
    workbook = xlrd.open_workbook(str(workbook_path), on_demand=True)
    try:
        sheet_names = tuple(workbook.sheet_names())
        if SHEET_NAME not in sheet_names:
            raise SourceIntegrityError(
                f"worksheet {SHEET_NAME!r} not found; observed {sheet_names!r}"
            )
        sheet = workbook.sheet_by_name(SHEET_NAME)
        variable_header = _normalize_header(sheet.row_values(0))
        field_header = _normalize_header(sheet.row_values(1))

        if variable_header != SOURCE_VARIABLE_HEADER:
            raise SourceIntegrityError(
                "source variable header mismatch: "
                f"expected {SOURCE_VARIABLE_HEADER!r}, observed {variable_header!r}"
            )
        if field_header != SOURCE_FIELD_HEADER:
            raise SourceIntegrityError(
                "source field header mismatch: "
                f"expected {SOURCE_FIELD_HEADER!r}, observed {field_header!r}"
            )
        if sheet.ncols != EXPECTED_COLUMNS:
            raise SourceIntegrityError(
                f"column count mismatch: expected {EXPECTED_COLUMNS}, observed {sheet.ncols}"
            )
        if sheet.nrows != EXPECTED_PHYSICAL_ROWS:
            raise SourceIntegrityError(
                f"physical row count mismatch: expected {EXPECTED_PHYSICAL_ROWS}, "
                f"observed {sheet.nrows}"
            )

        parsed_rows: list[tuple[int, ...]] = []
        rejected_cells: list[RejectedCell] = []
        seen_ids: set[int] = set()
        for row_index in range(2, sheet.nrows):
            parsed_row: list[int] = []
            row_rejected = False
            for column_index, raw_value in enumerate(sheet.row_values(row_index)):
                source_row_number = row_index + 1
                source_column_number = column_index + 1
                source_field = SOURCE_FIELD_HEADER[column_index]
                if raw_value in ("", None):
                    rejected_cells.append(
                        RejectedCell(
                            source_row_number=source_row_number,
                            source_column_number=source_column_number,
                            source_field=source_field,
                            reason="missing value; no imputation is permitted",
                            raw_value=repr(raw_value),
                        )
                    )
                    row_rejected = True
                    continue
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                    rejected_cells.append(
                        RejectedCell(
                            source_row_number=source_row_number,
                            source_column_number=source_column_number,
                            source_field=source_field,
                            reason="non-numeric source cell",
                            raw_value=repr(raw_value),
                        )
                    )
                    row_rejected = True
                    continue
                integer_value = int(raw_value)
                if raw_value != integer_value:
                    rejected_cells.append(
                        RejectedCell(
                            source_row_number=source_row_number,
                            source_column_number=source_column_number,
                            source_field=source_field,
                            reason="non-integral numeric value; rounding is not permitted",
                            raw_value=repr(raw_value),
                        )
                    )
                    row_rejected = True
                    continue
                if not POSTGRES_INTEGER_MIN <= integer_value <= POSTGRES_INTEGER_MAX:
                    rejected_cells.append(
                        RejectedCell(
                            source_row_number=source_row_number,
                            source_column_number=source_column_number,
                            source_field=source_field,
                            reason=(
                                "integral value is outside the lossless PostgreSQL integer range"
                            ),
                            raw_value=repr(raw_value),
                        )
                    )
                    row_rejected = True
                    continue
                parsed_row.append(integer_value)

            if row_rejected:
                continue
            row_values = tuple(parsed_row)
            source_id_value = row_values[0]
            if source_id_value in seen_ids:
                rejected_cells.append(
                    RejectedCell(
                        source_row_number=row_index + 1,
                        source_column_number=1,
                        source_field="ID",
                        reason="duplicate source ID; duplicate rows are not silently removed",
                        raw_value=repr(source_id_value),
                    )
                )
                continue
            seen_ids.add(source_id_value)
            parsed_rows.append(row_values)
    finally:
        workbook.release_resources()

    data_rows = sheet.nrows - 2
    if data_rows != EXPECTED_DATA_ROWS:
        raise SourceIntegrityError(
            f"data row count mismatch: expected {EXPECTED_DATA_ROWS}, observed {data_rows}"
        )
    if rejected_cells:
        rejected_rows = {item.source_row_number for item in rejected_cells}
        raise SourceIntegrityError(
            f"{len(rejected_cells)} source cells/keys were rejected; "
            "inspect the generated ingestion log",
            details={
                "reconciliation": {
                    "source_data_rows": data_rows,
                    "parsed_rows": len(parsed_rows),
                    "rejected_rows": len(rejected_rows),
                    "rejected_cells": len(rejected_cells),
                },
                "rejected_cells": [item.as_dict() for item in rejected_cells],
            },
        )
    if len(parsed_rows) != data_rows:
        raise SourceIntegrityError(
            f"row reconciliation failed: source has {data_rows} data rows, "
            f"parser accepted {len(parsed_rows)}"
        )

    return WorkbookInspection(
        archive_path=archive_path,
        archive_bytes=archive["bytes"],
        archive_sha256=archive["sha256"],
        archive_member=archive["member"],
        archive_member_bytes=archive["member_bytes"],
        archive_member_crc32=archive["member_crc32"],
        workbook_path=workbook_path,
        workbook_bytes=workbook_bytes,
        workbook_sha256=workbook_sha256,
        sheet_names=sheet_names,
        sheet_name=SHEET_NAME,
        physical_rows=sheet.nrows,
        data_rows=data_rows,
        columns=sheet.ncols,
        variable_header=variable_header,
        field_header=field_header,
        parsed_rows=tuple(parsed_rows),
        rejected_cells=tuple(rejected_cells),
    )


def _row_comparison(left_alias: str, right_alias: str) -> str:
    left = ", ".join(f"{left_alias}.{column}" for column in DATABASE_COLUMNS)
    right = ", ".join(f"{right_alias}.{column}" for column in DATABASE_COLUMNS)
    return f"ROW({left}) IS NOT DISTINCT FROM ROW({right})"


def _create_temporary_load_table(cursor: Any) -> None:
    definitions = ",\n                ".join(
        f"{column} integer NOT NULL" for column in DATABASE_COLUMNS
    )
    cursor.execute(
        f"""
        CREATE TEMPORARY TABLE raw_credit_card_client_load (
            source_row_number integer NOT NULL,
            {definitions},
            PRIMARY KEY (id)
        ) ON COMMIT DROP
        """
    )


def _copy_rows(cursor: Any, rows: Iterable[tuple[int, ...]]) -> None:
    copy_columns = ", ".join(("source_row_number", *DATABASE_COLUMNS))
    with cursor.copy(f"COPY raw_credit_card_client_load ({copy_columns}) FROM STDIN") as copy:
        for source_row_number, row in enumerate(rows, start=3):
            copy.write_row((source_row_number, *row))


def _register_source_file(connection: Any, inspection: WorkbookInspection) -> None:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.source_file (
                source_id,
                dataset_id,
                provider,
                source_url,
                doi,
                license,
                archive_path,
                archive_bytes,
                archive_sha256,
                file_path,
                file_name,
                file_bytes,
                file_sha256,
                worksheet,
                physical_row_count,
                data_row_count,
                column_count,
                header_row_count
            )
            VALUES (
                %(source_id)s,
                %(dataset_id)s,
                %(provider)s,
                %(source_url)s,
                %(doi)s,
                %(license)s,
                %(archive_path)s,
                %(archive_bytes)s,
                %(archive_sha256)s,
                %(file_path)s,
                %(file_name)s,
                %(file_bytes)s,
                %(file_sha256)s,
                %(worksheet)s,
                %(physical_row_count)s,
                %(data_row_count)s,
                %(column_count)s,
                2
            )
            ON CONFLICT (source_id, file_sha256) DO NOTHING
            """,
            {
                "source_id": SOURCE_ID,
                "dataset_id": DATASET_ID,
                "provider": PROVIDER,
                "source_url": LANDING_PAGE_URL,
                "doi": DOI,
                "license": LICENSE,
                "archive_path": repository_relative(inspection.archive_path),
                "archive_bytes": inspection.archive_bytes,
                "archive_sha256": inspection.archive_sha256,
                "file_path": repository_relative(inspection.workbook_path),
                "file_name": inspection.workbook_path.name,
                "file_bytes": inspection.workbook_bytes,
                "file_sha256": inspection.workbook_sha256,
                "worksheet": inspection.sheet_name,
                "physical_row_count": inspection.physical_rows,
                "data_row_count": inspection.data_rows,
                "column_count": inspection.columns,
            },
        )
        cursor.execute(
            """
            SELECT
                dataset_id,
                archive_sha256,
                file_bytes,
                worksheet,
                physical_row_count,
                data_row_count,
                column_count,
                header_row_count
            FROM audit.source_file
            WHERE source_id = %s
              AND file_sha256 = %s
            """,
            (SOURCE_ID, inspection.workbook_sha256),
        )
        observed = cursor.fetchone()
        expected = (
            DATASET_ID,
            inspection.archive_sha256,
            inspection.workbook_bytes,
            inspection.sheet_name,
            inspection.physical_rows,
            inspection.data_rows,
            inspection.columns,
            2,
        )
        if observed != expected:
            raise SourceIntegrityError(
                "existing audit.source_file metadata differs from the inspected source"
            )


def _start_ingestion_run(
    connection: Any,
    run_id: str,
    inspection: WorkbookInspection,
) -> None:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.ingestion_run (
                ingestion_run_id,
                source_id,
                source_file_sha256,
                started_at,
                status,
                source_row_count,
                rejected_row_count
            )
            VALUES (%s, %s, %s, clock_timestamp(), 'running', %s, 0)
            """,
            (run_id, SOURCE_ID, inspection.workbook_sha256, inspection.data_rows),
        )


def _mark_ingestion_failed(connection: Any, run_id: str, error: str) -> None:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE audit.ingestion_run
            SET completed_at = clock_timestamp(),
                status = 'failed',
                error_message = %s
            WHERE ingestion_run_id = %s
            """,
            (error[:4000], run_id),
        )


def load_database(
    database_url: str,
    inspection: WorkbookInspection,
    run_id: str,
    ddl_path: Path = DEFAULT_DDL_PATH,
) -> dict[str, int]:
    """Load source rows insert-only and prove repeat runs are exact no-ops."""

    _require_file(ddl_path, "raw DDL")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg>=3.2 is required for PostgreSQL ingestion") from exc

    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(ddl_path.read_text(encoding="utf-8"))
        _register_source_file(connection, inspection)
        _start_ingestion_run(connection, run_id, inspection)

        try:
            with connection.transaction(), connection.cursor() as cursor:
                _create_temporary_load_table(cursor)
                _copy_rows(cursor, inspection.parsed_rows)
                cursor.execute("SELECT count(*) FROM raw_credit_card_client_load")
                staged_rows = cursor.fetchone()[0]
                if staged_rows != inspection.data_rows:
                    raise SourceIntegrityError(
                        f"temporary-load reconciliation failed: expected "
                        f"{inspection.data_rows}, observed {staged_rows}"
                    )

                comparison = _row_comparison("r", "t")
                cursor.execute(
                    f"""
                    SELECT count(*)
                    FROM raw_credit_card_client_load AS t
                    JOIN raw.credit_card_client AS r
                      ON r.id = t.id
                    WHERE NOT ({comparison})
                       OR r.source_id <> %s
                       OR r.source_file_sha256 <> %s
                       OR r.source_row_number <> t.source_row_number
                    """,
                    (SOURCE_ID, inspection.workbook_sha256),
                )
                conflicting_rows = cursor.fetchone()[0]
                if conflicting_rows:
                    raise RawConflictError(
                        f"{conflicting_rows} existing raw rows differ from the "
                        "approved source; no rows were replaced"
                    )

                data_columns = ", ".join(DATABASE_COLUMNS)
                selected_columns = ", ".join(f"t.{column}" for column in DATABASE_COLUMNS)
                cursor.execute(
                    f"""
                    INSERT INTO raw.credit_card_client (
                        {data_columns},
                        source_id,
                        source_file_sha256,
                        source_row_number,
                        ingestion_run_id
                    )
                    SELECT
                        {selected_columns},
                        %s,
                        %s,
                        t.source_row_number,
                        %s
                    FROM raw_credit_card_client_load AS t
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM raw.credit_card_client AS r
                        WHERE r.id = t.id
                    )
                    ORDER BY t.source_row_number
                    """,
                    (SOURCE_ID, inspection.workbook_sha256, run_id),
                )
                inserted_rows = cursor.rowcount

                cursor.execute(
                    f"""
                    SELECT count(*)
                    FROM raw_credit_card_client_load AS t
                    JOIN raw.credit_card_client AS r
                      ON r.id = t.id
                    WHERE {comparison}
                      AND r.source_id = %s
                      AND r.source_file_sha256 = %s
                      AND r.source_row_number = t.source_row_number
                    """,
                    (SOURCE_ID, inspection.workbook_sha256),
                )
                matching_rows = cursor.fetchone()[0]
                if matching_rows != inspection.data_rows:
                    raise SourceIntegrityError(
                        f"raw reconciliation failed: expected {inspection.data_rows} "
                        f"matching rows, observed {matching_rows}"
                    )

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM raw.credit_card_client
                    WHERE source_id = %s
                      AND source_file_sha256 = %s
                    """,
                    (SOURCE_ID, inspection.workbook_sha256),
                )
                raw_source_rows = cursor.fetchone()[0]
                if raw_source_rows != inspection.data_rows:
                    raise SourceIntegrityError(
                        f"raw source-hash count failed: expected {inspection.data_rows}, "
                        f"observed {raw_source_rows}"
                    )

                existing_matching_rows = matching_rows - inserted_rows
                cursor.execute(
                    """
                    UPDATE audit.ingestion_run
                    SET completed_at = clock_timestamp(),
                        status = 'succeeded',
                        staged_row_count = %s,
                        inserted_row_count = %s,
                        existing_matching_row_count = %s,
                        raw_source_row_count = %s,
                        rejected_row_count = 0,
                        error_message = NULL
                    WHERE ingestion_run_id = %s
                    """,
                    (
                        staged_rows,
                        inserted_rows,
                        existing_matching_rows,
                        raw_source_rows,
                        run_id,
                    ),
                )
        except Exception as exc:
            _mark_ingestion_failed(connection, run_id, str(exc))
            raise

    return {
        "source_rows": inspection.data_rows,
        "staged_rows": staged_rows,
        "inserted_rows": inserted_rows,
        "existing_matching_rows": existing_matching_rows,
        "raw_source_rows": raw_source_rows,
        "rejected_rows": 0,
    }


def _safe_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
        raise ValueError("run ID must be 1-128 characters using letters, digits, '.', '_' or '-'")
    return run_id


def _default_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"uci350-{timestamp}-{uuid.uuid4().hex[:8]}"


def write_log(log_directory: Path, run_id: str, payload: dict[str, Any]) -> Path:
    """Create a new log without overwriting prior ingestion evidence."""

    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"{_safe_run_id(run_id)}.json"
    with log_path.open("x", encoding="utf-8") as target:
        json.dump(payload, target, ensure_ascii=False, indent=2, sort_keys=True)
        target.write("\n")
    return log_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or insert-only load the approved UCI dataset 350 workbook."
    )
    parser.add_argument("--archive-file", type=Path, default=DEFAULT_ARCHIVE_PATH)
    parser.add_argument("--source-file", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--ddl-file", type=Path, default=DEFAULT_DDL_PATH)
    parser.add_argument("--log-directory", type=Path, default=DEFAULT_LOG_DIRECTORY)
    parser.add_argument("--run-id", default=_default_run_id())
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="validate source/hash/schema and write a log without connecting to PostgreSQL",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL; defaults to DATABASE_URL and is required unless --inspect-only",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = _safe_run_id(args.run_id)
    mode = "inspect_only" if args.inspect_only else "database_load"
    started_at = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "run_id": run_id,
        "mode": mode,
        "started_at_utc": started_at,
        "status": "running",
    }
    exit_code = 1
    try:
        inspection = inspect_source(args.archive_file, args.source_file)
        payload.update(inspection.log_summary())
        if args.inspect_only:
            payload["database"] = {
                "attempted": False,
                "reason": "inspect-only mode",
            }
            payload["status"] = "inspected"
        else:
            if not args.database_url:
                raise RuntimeError(
                    "DATABASE_URL or --database-url is required for database loading"
                )
            database_reconciliation = load_database(
                args.database_url,
                inspection,
                run_id,
                args.ddl_file,
            )
            payload["database"] = {
                "attempted": True,
                "reconciliation": database_reconciliation,
            }
            payload["status"] = "loaded_and_reconciled"
        exit_code = 0
    except Exception as exc:
        payload["status"] = "failed"
        payload["error_type"] = type(exc).__name__
        payload["error"] = str(exc)
        if isinstance(exc, SourceIntegrityError):
            payload.update(exc.details)
    finally:
        payload["completed_at_utc"] = datetime.now(UTC).isoformat()
        try:
            log_path = write_log(args.log_directory, run_id, payload)
        except FileExistsError:
            print(
                f"refusing to overwrite existing ingestion log for run {run_id}",
                file=sys.stderr,
            )
            return 1

    print(json.dumps({"status": payload["status"], "log": str(log_path)}, sort_keys=True))
    if exit_code:
        print(payload.get("error", "ingestion failed"), file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
