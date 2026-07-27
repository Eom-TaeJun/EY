"""Export deterministic PostgreSQL facts for independent Wave 1 reproduction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import psycopg
import yaml


ROOT = Path(__file__).resolve().parents[1]
ENFORCED_DQ_IDS = tuple(f"DQ-{number:03d}" for number in range(1, 16))


def _one(cursor: Any, query: str, params: tuple[Any, ...]) -> Any:
    cursor.execute(query, params)
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("required query returned no row")
    return row[0]


def _rows(cursor: Any, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    cursor.execute(query, params)
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _signal_definitions() -> tuple[str, list[dict[str, Any]]]:
    config_path = ROOT / "config/risk_definitions.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("signals"), dict):
        raise RuntimeError("config/risk_definitions.yml has no signals mapping")
    version = config.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("risk definition version is required")
    definitions: list[dict[str, Any]] = []
    for signal_id, definition in config["signals"].items():
        if not isinstance(definition, dict) or definition.get("status") != "active":
            continue
        definitions.append(
            {
                "signal_id": signal_id,
                "economic_rationale": definition["economic_rationale"],
                "observation_timing": definition["observation_timing"],
                "timing_status": definition["timing_status"],
                "leakage_status": definition["leakage_status"],
                "sql_artifact": "sql/features/060_risk_signals.sql",
            }
        )
    return version, definitions


def build_snapshot(database_url: str, run_id: str) -> dict[str, Any]:
    version, definitions = _signal_definitions()
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SET jit = off")
        pipeline = _rows(
            cursor,
            """
            SELECT source_id, source_file_sha256
            FROM audit.pipeline_run
            WHERE pipeline_run_id = %s
              AND status IN ('succeeded', 'validated')
            """,
            (run_id,),
        )
        if len(pipeline) != 1:
            raise RuntimeError(f"run {run_id!r} is missing or not succeeded/validated")
        source_id = pipeline[0]["source_id"]
        source_hash = pipeline[0]["source_file_sha256"]

        source = _rows(
            cursor,
            """
            SELECT
                source_id,
                data_row_count AS source_rows,
                column_count AS source_columns,
                file_sha256 AS sha256
            FROM audit.source_file
            WHERE source_id = %s AND file_sha256 = %s
            """,
            (source_id, source_hash),
        )
        if len(source) != 1:
            raise RuntimeError("run source is not uniquely registered")
        source_fact = source[0]
        raw_rows = _one(
            cursor,
            """
            SELECT count(*)
            FROM raw.credit_card_client
            WHERE source_id = %s AND source_file_sha256 = %s
            """,
            (source_id, source_hash),
        )
        rejected_rows = _one(
            cursor,
            """
            SELECT coalesce(max(rejected_row_count), 0)
            FROM audit.ingestion_run
            WHERE source_id = %s
              AND source_file_sha256 = %s
              AND status = 'succeeded'
            """,
            (source_id, source_hash),
        )

        core_counts = _rows(
            cursor,
            """
            SELECT
                (SELECT count(*) FROM core.borrower WHERE pipeline_run_id = %s)
                    AS borrower_rows,
                (SELECT count(*) FROM core.account_month WHERE pipeline_run_id = %s)
                    AS account_month_rows,
                (SELECT count(DISTINCT month_offset) FROM core.account_month
                 WHERE pipeline_run_id = %s) AS months_per_borrower
            """,
            (run_id, run_id, run_id),
        )[0]
        integrity = _rows(
            cursor,
            """
            SELECT
                (SELECT count(*) FROM (
                    SELECT customer_id FROM core.borrower
                    WHERE pipeline_run_id = %s
                    GROUP BY customer_id HAVING count(*) > 1
                ) AS duplicated) AS duplicate_borrower_keys,
                (SELECT count(*) FROM (
                    SELECT customer_id, month_offset FROM core.account_month
                    WHERE pipeline_run_id = %s
                    GROUP BY customer_id, month_offset HAVING count(*) > 1
                ) AS duplicated) AS duplicate_account_month_keys,
                (SELECT count(*) FROM core.borrower
                 WHERE pipeline_run_id = %s AND customer_id IS NULL)
                    AS null_borrower_keys,
                (SELECT count(*)
                 FROM core.account_month AS account
                 LEFT JOIN core.borrower AS borrower
                   ON borrower.pipeline_run_id = account.pipeline_run_id
                  AND borrower.customer_id = account.customer_id
                 WHERE account.pipeline_run_id = %s
                   AND borrower.customer_id IS NULL) AS orphan_account_month_rows,
                (SELECT count(*) FROM core.borrower
                 WHERE pipeline_run_id = %s
                   AND (
                     next_month_default NOT IN (0, 1)
                     OR sex_code NOT IN (1, 2)
                     OR credit_limit_ntd <= 0
                     OR age_years NOT BETWEEN 18 AND 120
                   )) AS invalid_code_rows,
                (SELECT count(*) FROM core.account_month
                 WHERE pipeline_run_id = %s
                   AND (
                     repayment_status IS NULL
                     OR bill_amount_ntd IS NULL
                     OR payment_amount_ntd IS NULL
                   )) AS missing_required_history_rows
            """,
            (run_id, run_id, run_id, run_id, run_id, run_id),
        )[0]
        reconciliations = {
            row["reconciliation_id"]: row
            for row in _rows(
                cursor,
                """
                SELECT reconciliation_id, source_value, derived_value, status
                FROM audit.reconciliation_result
                WHERE pipeline_run_id = %s
                  AND reconciliation_id IN ('REC-003', 'REC-004')
                """,
                (run_id,),
            )
        }
        if set(reconciliations) != {"REC-003", "REC-004"}:
            raise RuntimeError("required amount reconciliations are missing")

        enforced_tests = _rows(
            cursor,
            """
            SELECT test_id, status, tested_rows, failed_rows, severity, affected_object
            FROM audit.test_result
            WHERE pipeline_run_id = %s AND test_id = ANY(%s)
            ORDER BY test_id
            """,
            (run_id, list(ENFORCED_DQ_IDS)),
        )
        warnings = _rows(
            cursor,
            """
            SELECT test_id, status, tested_rows, failed_rows, severity, affected_object
            FROM audit.test_result
            WHERE pipeline_run_id = %s AND status = 'warn'
            ORDER BY test_id
            """,
            (run_id,),
        )
        outcomes = _rows(
            cursor,
            """
            SELECT
                signal_name AS signal_id,
                signal_bucket AS bucket,
                sample_size AS sample_count,
                default_count
            FROM mart.signal_default_summary
            WHERE pipeline_run_id = %s
            ORDER BY signal_name, bucket_order
            """,
            (run_id,),
        )
        risk_bands = _rows(
            cursor,
            """
            SELECT risk_band, sample_size AS sample_count, default_count
            FROM mart.risk_band_summary
            WHERE pipeline_run_id = %s
            ORDER BY band_order
            """,
            (run_id,),
        )

    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "source": {
            "registered": True,
            "source_id": source_id,
            "registry_path": "docs/data/source_registry.md",
            "sha256": source_fact["sha256"],
            "source_rows": source_fact["source_rows"],
            "source_columns": source_fact["source_columns"],
            "raw_rows": raw_rows,
            "unlogged_rejects": max(
                source_fact["source_rows"] - raw_rows - rejected_rows,
                0,
            ),
        },
        "core": {
            **core_counts,
            **integrity,
            "bill_wide_total": str(reconciliations["REC-003"]["source_value"]),
            "bill_long_total": str(reconciliations["REC-003"]["derived_value"]),
            "payment_wide_total": str(reconciliations["REC-004"]["source_value"]),
            "payment_long_total": str(reconciliations["REC-004"]["derived_value"]),
        },
        "sql_tests": enforced_tests,
        "sql_warnings": warnings,
        "signals": {
            "definition_version": version,
            "definitions": definitions,
            "outcomes": outcomes,
            "risk_bands": risk_bands,
            "query_manifest": "sql/features/MANIFEST.md",
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/qa/wave1_snapshot.json",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot = build_snapshot(args.database_url, args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(snapshot, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
    print(f"Wave 1 snapshot created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
