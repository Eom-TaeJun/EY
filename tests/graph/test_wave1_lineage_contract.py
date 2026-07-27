"""Static fail-closed checks for the validated Wave 1 lineage registration."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINEAGE_SQL = ROOT / "sql" / "ddl" / "031_wave1_lineage.sql"
VALIDATION = (
    ROOT
    / "outputs"
    / "qa"
    / "validated"
    / "latest"
    / "wave1_independent_validation.json"
)
EXPECTED_FEATURES = {
    "recent_max_delinquency",
    "delinquent_months_6m",
    "delinquency_deterioration",
    "latest_utilization_ratio",
    "payment_coverage_ratio",
    "zero_payment_streak",
    "recent_bill_growth",
}


def _validation() -> dict[str, object]:
    return json.loads(VALIDATION.read_text(encoding="utf-8"))


def test_lineage_is_pinned_to_the_independently_validated_evidence() -> None:
    sql = LINEAGE_SQL.read_text(encoding="utf-8")
    validation = _validation()
    gate_packets = validation["gate_packets"]
    assert isinstance(gate_packets, list)
    gate_1 = next(packet for packet in gate_packets if packet["gate"] == 1)
    sha_check = next(
        check for check in gate_1["checks"] if check["check_id"] == "sha256_recorded"
    )
    source_sha256 = sha_check["evidence"]["sha256"]
    validation_sha256 = hashlib.sha256(VALIDATION.read_bytes()).hexdigest()

    assert validation["status"] == "pass"
    assert validation["issues"] == []
    assert validation["run_id"] in sql
    assert source_sha256 in sql
    assert validation_sha256 in sql
    assert VALIDATION.relative_to(ROOT).as_posix() in sql


def test_lineage_registers_exactly_the_seven_validated_features() -> None:
    sql = LINEAGE_SQL.read_text(encoding="utf-8")
    validation = _validation()
    findings = validation["verified_findings"]
    assert isinstance(findings, dict)
    outcomes = findings["signal_outcomes"]
    assert isinstance(outcomes, list)
    validated_features = {row["signal_id"] for row in outcomes}

    loop_values = re.search(
        r"FOR v_feature_name IN(?P<body>.*?)ORDER BY feature\.feature_name",
        sql,
        flags=re.DOTALL,
    )
    assert loop_values is not None
    registered_features = set(
        re.findall(r"\('([a-z0-9_]+)'\)", loop_values.group("body"))
    )

    assert validated_features == EXPECTED_FEATURES
    assert registered_features == EXPECTED_FEATURES


def test_lineage_uses_only_data_lineage_and_existing_repository_paths() -> None:
    sql = LINEAGE_SQL.read_text(encoding="utf-8")
    required_paths = {
        "src/ingestion/load_uci_credit_card.py",
        "sql/ingestion/001_raw_credit_card_client.sql",
        "sql/staging/020_build_core.sql",
        "sql/features/060_risk_signals.sql",
        "sql/reporting/070_signal_summaries.sql",
        "src/validation/wave1_reproduction.py",
        "outputs/qa/validated/latest/wave1_independent_validation.json",
    }

    assert "c_scope constant text := 'data_lineage'" in sql
    assert "'economic_transmission'" not in sql
    # Raw source files are intentionally Git-ignored and are verified by the
    # pinned SHA-256 rather than required in every clean-clone test checkout.
    assert "data/raw/default of credit card clients.xls" in sql
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file()
        assert relative_path in sql
