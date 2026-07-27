"""Run the Wave 2 cross-sectional PD prototype from PostgreSQL.

Purpose:
    Read the validated Wave 1 model population, fit three deterministic PD
    prototypes, and write an immutable JSON evidence candidate.
Inputs:
    PostgreSQL connection string, source/model run IDs, generated-at timestamp,
    and sql/risk_components/100_pd_model_extract.sql.
Outputs:
    A new JSON file opened in exclusive-create mode; existing evidence is never
    overwritten.
Observation point:
    The source run's single borrower observation date. This command does not
    create a time-aware validation claim.
Key assumptions:
    The supplied source run has passed Gates 1-3. Database reads are read-only;
    this builder does not independently approve its own packet.
Validation:
    src.models.pd_prototype assertions, tests/models, and the independently
    owned Wave 2 validator recompute the row-level metrics and Gate 4 status.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import pandas as pd
import psycopg

from src.models.pd_prototype import MODEL_DEFINITION_VERSION, build_model_packet


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQL_PATH = REPOSITORY_ROOT / "sql/risk_components/100_pd_model_extract.sql"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--model-run-id", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument(
        "--model-definition-version", default=MODEL_DEFINITION_VERSION
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sql-path", type=Path, default=DEFAULT_SQL_PATH)
    return parser


def _load_frame(database_url: str, source_run_id: str, sql_path: Path) -> pd.DataFrame:
    sql_text = sql_path.read_text(encoding="utf-8")
    marker = "-- MODEL_QUERY_START"
    if marker not in sql_text:
        raise ValueError(f"model extract SQL is missing required marker: {marker}")
    setup_sql, query = sql_text.split(marker, maxsplit=1)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(setup_sql)
            cursor.execute(query, {"source_run_id": source_run_id})
            columns = [column.name for column in cursor.description or ()]
            rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing model evidence: {args.output}")
    frame = _load_frame(args.database_url, args.source_run_id, args.sql_path)
    packet = build_model_packet(
        frame,
        source_run_id=args.source_run_id,
        model_run_id=args.model_run_id,
        generated_at=args.generated_at,
        model_definition_version=args.model_definition_version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(packet, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "status": packet["status"],
                "source_run_id": args.source_run_id,
                "model_run_id": args.model_run_id,
                "borrowers": packet["source_metadata"]["borrower_count"],
                "test_rows": packet["validation_design"]["split_counts"]["test"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
