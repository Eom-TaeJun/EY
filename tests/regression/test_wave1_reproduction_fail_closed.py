"""Regression tests for independent Wave 1 arithmetic and stopping rules."""

from __future__ import annotations

from copy import deepcopy

from src.validation.wave1_reproduction import reproduce_wave1


def _valid_snapshot() -> dict[str, object]:
    signal_ids = [f"signal_{index}" for index in range(1, 6)]
    definitions = [
        {
            "signal_id": signal_id,
            "economic_rationale": f"economic rationale for {signal_id}",
            "observation_timing": "six source history months before target",
            "timing_status": "pass",
            "leakage_status": "pass",
            "sql_artifact": f"sql/features/{signal_id}.sql",
        }
        for signal_id in signal_ids
    ]
    outcomes = [
        {
            "signal_id": signal_id,
            "bucket": bucket,
            "sample_count": 5,
            "default_count": defaults,
        }
        for signal_id in signal_ids
        for bucket, defaults in (("lower", 1), ("higher", 2))
    ]
    return {
        "schema_version": "1.0",
        "run_id": "RUN-TEST-001",
        "source": {
            "source_id": "uci_default_credit_card_clients",
            "registry_path": "docs/data/source_registry.md",
            "sha256": "b" * 64,
            "source_rows": 10,
            "source_columns": 25,
            "raw_rows": 10,
            "unlogged_rejects": 0,
            "registered": True,
        },
        "core": {
            "borrower_rows": 10,
            "account_month_rows": 60,
            "months_per_borrower": 6,
            "duplicate_borrower_keys": 0,
            "duplicate_account_month_keys": 0,
            "null_borrower_keys": 0,
            "orphan_account_month_rows": 0,
            "invalid_code_rows": 0,
            "missing_required_history_rows": 0,
            "bill_wide_total": "1234.00",
            "bill_long_total": "1234.00",
            "payment_wide_total": "456.00",
            "payment_long_total": "456.00",
        },
        "sql_tests": [
            {
                "test_id": f"DQ-{index:03d}",
                "status": "pass",
                "tested_rows": 10,
                "failed_rows": 0,
                "severity": "critical" if index <= 6 else "high",
                "affected_object": "core.borrower",
            }
            for index in range(1, 13)
        ],
        "signals": {
            "definition_version": "0.1.0",
            "query_manifest": "sql/features/manifest.json",
            "definitions": definitions,
            "outcomes": outcomes,
            "risk_bands": [
                {
                    "risk_band": "lower",
                    "sample_count": 5,
                    "default_count": 1,
                },
                {
                    "risk_band": "higher",
                    "sample_count": 5,
                    "default_count": 2,
                },
            ],
        },
    }


def test_complete_snapshot_reproduces_all_wave1_gates() -> None:
    report = reproduce_wave1(
        _valid_snapshot(),
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.status == "pass"
    assert [packet["status"] for packet in report.gate_packets] == [
        "pass",
        "pass",
        "pass",
    ]
    assert all(contract.valid for contract in report.contract_reports)
    assert report.verified_findings["account_month_rows"] == 60
    assert report.verified_findings["sql_test_count"] == 12
    signal_rows = report.verified_findings["signal_outcomes"]
    assert signal_rows[0]["observed_default_rate"] == "0.2"


def test_missing_source_evidence_cannot_pass_any_downstream_gate() -> None:
    snapshot = _valid_snapshot()
    source = snapshot["source"]
    assert isinstance(source, dict)
    source.pop("raw_rows")

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.status != "pass"
    assert [packet["status"] for packet in report.gate_packets] == [
        "fail",
        "fail",
        "fail",
    ]
    assert report.verified_findings == {}


def test_fewer_than_twelve_sql_tests_blocks_gate_2_and_gate_3() -> None:
    snapshot = _valid_snapshot()
    sql_tests = snapshot["sql_tests"]
    assert isinstance(sql_tests, list)
    snapshot["sql_tests"] = sql_tests[:11]

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.gate_packets[0]["status"] == "pass"
    assert report.gate_packets[1]["status"] == "fail"
    assert report.gate_packets[2]["status"] == "fail"
    assert "insufficient_sql_tests" in {issue.code for issue in report.issues}


def test_account_month_mismatch_is_not_masked_by_reported_values() -> None:
    snapshot = _valid_snapshot()
    core = snapshot["core"]
    assert isinstance(core, dict)
    core["account_month_rows"] = 59

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.status == "fail"
    assert "account_month_row_mismatch" in {issue.code for issue in report.issues}
    assert report.gate_packets[1]["status"] == "fail"


def test_signal_population_mismatch_blocks_signal_gate() -> None:
    snapshot = _valid_snapshot()
    signals = snapshot["signals"]
    assert isinstance(signals, dict)
    outcomes = signals["outcomes"]
    assert isinstance(outcomes, list)
    tampered = deepcopy(outcomes[0])
    tampered["sample_count"] = 4
    outcomes[0] = tampered

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.gate_packets[0]["status"] == "pass"
    assert report.gate_packets[1]["status"] == "pass"
    assert report.gate_packets[2]["status"] == "fail"
    assert "outcome_population_mismatch" in {
        issue.code for issue in report.issues
    }


def test_empty_or_non_object_snapshot_is_blocked_without_gate_packets() -> None:
    report = reproduce_wave1(
        None,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.status == "blocked"
    assert report.gate_packets == ()
    assert report.contract_reports == ()
    assert report.verified_findings == {}


def test_malformed_list_item_is_not_silently_discarded() -> None:
    snapshot = _valid_snapshot()
    sql_tests = snapshot["sql_tests"]
    assert isinstance(sql_tests, list)
    sql_tests.append("not a test record")

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.status == "fail"
    assert report.gate_packets[1]["status"] == "fail"
    assert "malformed_list_item" in {issue.code for issue in report.issues}


def test_account_month_composite_key_duplicates_block_core_gate() -> None:
    snapshot = _valid_snapshot()
    core = snapshot["core"]
    assert isinstance(core, dict)
    core["duplicate_account_month_keys"] = 1

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.gate_packets[0]["status"] == "pass"
    assert report.gate_packets[1]["status"] == "fail"
    assert report.gate_packets[2]["status"] == "fail"
    assert "core_integrity_failure" in {issue.code for issue in report.issues}


def test_signal_and_risk_band_default_totals_must_reconcile() -> None:
    snapshot = _valid_snapshot()
    signals = snapshot["signals"]
    assert isinstance(signals, dict)
    risk_bands = signals["risk_bands"]
    assert isinstance(risk_bands, list)
    changed = deepcopy(risk_bands[1])
    changed["default_count"] = 3
    risk_bands[1] = changed

    report = reproduce_wave1(
        snapshot,
        generated_at="2026-07-27T12:00:00+09:00",
    )

    assert report.gate_packets[2]["status"] == "fail"
    assert "default_total_mismatch" in {issue.code for issue in report.issues}
