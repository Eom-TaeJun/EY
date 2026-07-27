"""Integration tests for the gate packet boundary contract."""

from __future__ import annotations

import json

import pytest

from src.validation.gate_evidence import (
    DuplicateJsonKeyError,
    GateEvidenceValidator,
    load_json_object,
    load_thresholds,
)


def _valid_gate_1_packet() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "gate": 1,
        "run_id": "RUN-TEST-001",
        "generated_at": "2026-07-27T12:00:00+09:00",
        "producer": {
            "role": "Validation",
            "command": "python -m src.validation.wave1_reproduction",
        },
        "status": "pass",
        "checks": [
            {
                "check_id": "source_registered",
                "status": "pass",
                "evidence": {
                    "registered": True,
                    "source_id": "uci_default_credit_card_clients",
                    "registry_path": "docs/data/source_registry.md",
                },
            },
            {
                "check_id": "sha256_recorded",
                "status": "pass",
                "evidence": {"sha256": "a" * 64},
            },
            {
                "check_id": "source_shape_recorded",
                "status": "pass",
                "evidence": {"source_rows": 10, "source_columns": 25},
            },
            {
                "check_id": "raw_rows_reconciled",
                "status": "pass",
                "evidence": {
                    "source_rows": 10,
                    "raw_rows": 10,
                    "difference": 0,
                    "unlogged_rejects": 0,
                },
            },
        ],
    }


def test_valid_gate_1_packet_is_release_eligible() -> None:
    report = GateEvidenceValidator().validate(
        _valid_gate_1_packet(),
        expected_gate=1,
        expected_run_id="RUN-TEST-001",
    )

    assert report.valid is True
    assert report.issues == ()


def test_duplicate_check_id_fails_closed() -> None:
    packet = _valid_gate_1_packet()
    checks = packet["checks"]
    assert isinstance(checks, list)
    checks.append(dict(checks[0]))

    report = GateEvidenceValidator().validate(packet)

    assert report.valid is False
    assert "duplicate_check_id" in {issue.code for issue in report.issues}


def test_truthy_but_unstructured_evidence_is_rejected() -> None:
    packet = _valid_gate_1_packet()
    checks = packet["checks"]
    assert isinstance(checks, list)
    checks[1]["evidence"] = "hash exists"

    report = GateEvidenceValidator().validate(packet)

    assert report.valid is False
    assert "invalid_evidence" in {issue.code for issue in report.issues}


def test_tampered_row_difference_is_recomputed() -> None:
    packet = _valid_gate_1_packet()
    checks = packet["checks"]
    assert isinstance(checks, list)
    checks[3]["evidence"] = {
        "source_rows": 10,
        "raw_rows": 9,
        "difference": 0,
        "unlogged_rejects": 0,
    }

    report = GateEvidenceValidator().validate(packet)

    assert report.valid is False
    messages = " ".join(issue.message for issue in report.issues)
    assert "raw_rows must exactly equal source_rows" in messages


def test_expected_run_id_mismatch_is_rejected() -> None:
    report = GateEvidenceValidator().validate(
        _valid_gate_1_packet(),
        expected_run_id="RUN-OTHER-001",
    )

    assert report.valid is False
    assert "unexpected_run_id" in {issue.code for issue in report.issues}


def test_loader_rejects_duplicate_json_keys(tmp_path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"gate": 1, "gate": 2}', encoding="utf-8")

    with pytest.raises(DuplicateJsonKeyError):
        load_json_object(path)


def test_loader_rejects_non_finite_json_numbers(tmp_path) -> None:
    path = tmp_path / "nan.json"
    path.write_text(json.dumps({"gate": float("nan")}), encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite"):
        load_json_object(path)


def test_missing_referenced_artifact_fails_when_repository_root_is_supplied(
    tmp_path,
) -> None:
    report = GateEvidenceValidator(artifact_root=tmp_path).validate(
        _valid_gate_1_packet()
    )

    assert report.valid is False
    assert "missing_artifact" in {issue.code for issue in report.issues}


def test_threshold_loader_rejects_missing_required_keys(tmp_path) -> None:
    path = tmp_path / "thresholds.yml"
    path.write_text("reconciliation: {}\nquality: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="row_count_difference"):
        load_thresholds(path)
