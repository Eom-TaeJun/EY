from __future__ import annotations

import copy
import hashlib
import math

import pytest

from src.validation.wave2_validation import (
    BEHAVIORAL_FEATURES,
    COMBINED_FEATURES,
    EXCLUDED_FEATURES,
    FEATURE_ALLOWLISTS,
    STATIC_FEATURES,
    _write_new_json,
    _calculate_metrics,
    _calculate_segment_stability,
    validate_wave2,
)


SPLIT_VERSION = "customer_sha256_v1"


def _population() -> list[dict[str, object]]:
    defaults = {5, 10, 14, 15, 20, 30}
    ranked = sorted(
        (
            hashlib.sha256(f"{SPLIT_VERSION}:{borrower_id}".encode()).digest(),
            borrower_id,
        )
        for borrower_id in range(1, 31)
    )
    split_by_id: dict[int, str] = {}
    for rank, (_, borrower_id) in enumerate(ranked):
        split_by_id[borrower_id] = (
            "train" if rank < 18 else "calibration" if rank < 24 else "test"
        )
    return [
        {
            "borrower_id": borrower_id,
            "actual_default": int(borrower_id in defaults),
            "split": split_by_id[borrower_id],
            "sex_code": 1 + borrower_id % 2,
            "education_code": 1 + borrower_id % 3,
            "marriage_code": borrower_id % 3,
            "age_band": ("<30", "30-39", "40-49")[borrower_id % 3],
            "risk_band": ("Low", "Medium", "High")[borrower_id % 3],
        }
        for borrower_id in range(1, 31)
    ]


def _model(
    name: str,
    population: list[dict[str, object]],
    *,
    shift: float,
) -> dict[str, object]:
    predictions: list[dict[str, object]] = []
    for row in population:
        if row["split"] != "test":
            continue
        raw_pd = min(0.85, 0.08 + int(row["borrower_id"]) * 0.015 + shift)
        slope = 0.9 + shift
        intercept = -0.05 + shift
        logit = math.log(raw_pd / (1 - raw_pd))
        calibrated = 1 / (1 + math.exp(-(intercept + slope * logit)))
        predictions.append(
            {
                "borrower_id": row["borrower_id"],
                "actual_default": row["actual_default"],
                "raw_pd": raw_pd,
                "predicted_pd": calibrated,
                "split": "test",
            }
        )
    issues = []
    metrics = _calculate_metrics(predictions, issues, f"$.models.{name}")
    assert metrics is not None
    assert not issues
    normalized_population = {str(row["borrower_id"]): row for row in population}
    segments = _calculate_segment_stability(predictions, normalized_population)
    return {
        "model_run_id": "W2-TEST-001",
        "model_definition_version": "0.2.0",
        "feature_names": list(FEATURE_ALLOWLISTS[name]),
        "fit_counts": {"train": 18, "calibration": 6, "test": 6},
        "preprocessing": {"fit_population": "train_only"},
        "calibration": {
            "method": "platt_on_disjoint_calibration",
            "fit_population": "calibration_only",
            "platt_fit_slope": slope,
            "platt_fit_intercept": intercept,
        },
        "metrics": {
            "test": {
                "method": "descriptive_logistic_actual_on_logit_predicted",
                "use": "diagnostic_only_not_refit",
                "sample_count": metrics.sample_count,
                "default_count": metrics.default_count,
                "default_rate": metrics.default_rate,
                "average_pd": metrics.average_pd,
                "roc_auc": metrics.roc_auc,
                "pr_auc": metrics.pr_auc,
                "brier_score": metrics.brier_score,
                "log_loss": metrics.log_loss,
                "expected_calibration_error_10_bin": (
                    metrics.expected_calibration_error_10_bin
                ),
                "calibration_intercept": metrics.test_calibration_intercept,
                "calibration_slope": metrics.test_calibration_slope,
            }
        },
        "segment_stability": segments,
        "test_predictions": predictions,
    }


def _artifact() -> dict[str, object]:
    population = _population()
    source_hash = "a" * 64
    models = {
        "static": _model("static", population, shift=0.00),
        "behavioral": _model("behavioral", population, shift=0.02),
        "combined": _model("combined", population, shift=0.04),
    }
    static_metrics = models["static"]["metrics"]["test"]
    comparison = {}
    for name, model in models.items():
        metrics = model["metrics"]["test"]
        comparison[name] = {
            "test_roc_auc_delta_vs_static": (
                metrics["roc_auc"] - static_metrics["roc_auc"]
            ),
            "test_pr_auc_delta_vs_static": (
                metrics["pr_auc"] - static_metrics["pr_auc"]
            ),
            "test_brier_delta_vs_static": (
                metrics["brier_score"] - static_metrics["brier_score"]
            ),
        }
    return {
        "schema_version": "1.0",
        "run_id": "W2-TEST-001",
        "model_run_id": "W2-TEST-001",
        "source_run_id": "W1-TEST-001",
        "source_sha256": source_hash,
        "definition_version": "0.2.0",
        "model_definition_version": "0.2.0",
        "generated_at": "2026-07-27T12:00:00+00:00",
        "status": "retrospective_internal_benchmark_only",
        "source_metadata": {
            "source_id": "uci_default_credit_card_clients",
            "source_file_sha256": source_hash,
            "source_definition_version": "0.1.0",
            "observation_date": "2005-09-30",
            "borrower_count": 30,
            "observed_default_count": 6,
        },
        "validation_design": {
            "strategy": "stable_customer_id_sha256_rank_60_20_20",
            "split_version": SPLIT_VERSION,
            "split_algorithm": "sha256_rank",
            "split_input_contract": (
                "UTF-8 bytes of split_version + ':' + base-10 integer borrower_id"
            ),
            "split_order": "ascending_full_hex_digest_then_borrower_id",
            "split_key": "customer_id",
            "train_fraction": 0.6,
            "calibration_fraction": 0.2,
            "test_fraction": 0.2,
            "split_thresholds": {
                "train_rank_end_exclusive": 18,
                "calibration_rank_end_exclusive": 24,
                "population_size": 30,
            },
            "split_counts": {"train": 18, "calibration": 6, "test": 6},
            "genuine_time_direction": False,
            "temporal_gate_eligible": False,
            "reason": "one common observation date",
        },
        "feature_controls": {
            "allowlists": {
                "static": list(STATIC_FEATURES),
                "behavioral": list(BEHAVIORAL_FEATURES),
                "combined": list(COMBINED_FEATURES),
            },
            "excluded_features": sorted(EXCLUDED_FEATURES),
            "preprocessing_fit_split": "train",
            "calibration_fit_split": "calibration",
        },
        "leakage_controls": {
            "outcome_field": "next_month_default",
            "forbidden_features": sorted(EXCLUDED_FEATURES),
            "feature_timing_status": "wave1_gate3_passed_but_single_observation_date",
            "checks": [
                "explicit_allowlist_features_only",
                "target_not_in_feature_matrix",
                "identifiers_dates_run_source_metadata_excluded",
                "risk_points_and_risk_band_excluded",
                "preprocessing_fit_on_train_only",
                "calibration_fit_on_calibration_only",
                "test_used_for_final_evaluation_only",
            ],
        },
        "population": population,
        "models": models,
        "comparison": comparison,
        "component_scope": {
            "pd": {"status": "prototype_retrospective_internal_benchmark"},
            "stage": {"status": "not_estimated"},
            "ead": {"status": "not_estimated"},
            "lgd": {"status": "not_estimated"},
            "ecl": {"status": "not_estimated"},
            "scenario_sensitivity": {"status": "deferred"},
        },
    }


def _validate(artifact: dict[str, object]):
    return validate_wave2(
        artifact,
        generated_at="2026-07-27T12:00:00+00:00",
        expected_population_count=30,
        expected_default_count=6,
        expected_source_run_id="W1-TEST-001",
        expected_source_sha256="a" * 64,
    )


def test_valid_non_temporal_packet_is_blocked_not_approved() -> None:
    report = _validate(_artifact())

    assert report.status == "blocked"
    assert report.gate_4_eligible is False
    assert {issue.code for issue in report.issues} == {
        "time_direction_unavailable",
        "sensitivity_unavailable",
    }
    assert set(report.recomputed_metrics) == {"static", "behavioral", "combined"}
    assert report.to_dict()["approval"] == "not_granted"


def test_tampered_probability_and_reported_metric_fail_closed() -> None:
    artifact = _artifact()
    static = artifact["models"]["static"]
    static["test_predictions"][0]["predicted_pd"] = 1.5
    static["metrics"]["test"]["roc_auc"] = 0.999

    report = _validate(artifact)
    codes = {issue.code for issue in report.issues}

    assert report.status == "fail"
    assert report.gate_4_eligible is False
    assert "invalid_probability" in codes
    assert "reported_metric_mismatch" in codes


def test_tampered_hash_split_and_run_version_fail_closed() -> None:
    artifact = _artifact()
    first_train = next(row for row in artifact["population"] if row["split"] == "train")
    first_test = next(row for row in artifact["population"] if row["split"] == "test")
    first_train["split"], first_test["split"] = first_test["split"], first_train["split"]
    artifact["models"]["combined"]["model_definition_version"] = "tampered"

    report = _validate(artifact)
    codes = {issue.code for issue in report.issues}

    assert report.status == "fail"
    assert "cryptographic_split_mismatch" in codes
    assert "model_definition_version_mismatch" in codes


def test_duplicate_prediction_and_outcome_tampering_fail_closed() -> None:
    artifact = _artifact()
    rows = artifact["models"]["behavioral"]["test_predictions"]
    rows[1]["borrower_id"] = rows[0]["borrower_id"]
    rows[2]["actual_default"] = 1 - rows[2]["actual_default"]

    report = _validate(copy.deepcopy(artifact))
    codes = {issue.code for issue in report.issues}

    assert report.status == "fail"
    assert "duplicate_prediction_id" in codes
    assert "prediction_outcome_mismatch" in codes


def test_validation_output_refuses_overwrite(tmp_path) -> None:
    output = tmp_path / "wave2-validation.json"
    _write_new_json(output, {"status": "blocked"})

    with pytest.raises(FileExistsError):
        _write_new_json(output, {"status": "tampered"})

    assert output.read_text(encoding="utf-8").count("blocked") == 1
