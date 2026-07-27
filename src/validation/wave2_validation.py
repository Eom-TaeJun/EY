"""Independently validate one Wave 2 PD model result.

The Builder artifact is evidence, not authority.  This module reconstructs the
test population, metrics, calibration bins, model comparisons, and segment
summaries from row-level predictions.  It does not import Builder code or
approve Gate 4.

The current UCI source has no borrower-level observation timestamp.  Therefore
an otherwise valid deterministic split is reported as ``blocked`` for Gate 4
when ``validation_design.genuine_time_direction`` is false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .gate_evidence import ValidationIssue, load_json_object


MODEL_NAMES = ("static", "behavioral", "combined")
SPLIT_NAMES = ("train", "calibration", "test")
SEGMENT_FIELDS = (
    "sex_code",
    "education_code",
    "marriage_code",
    "age_band",
    "risk_band",
)
EXPECTED_POPULATION_COUNT = 30_000
EXPECTED_DEFAULT_COUNT = 6_636
EXPECTED_SOURCE_RUN_ID = "W1-20260727-001"
EXPECTED_SOURCE_SHA256 = (
    "30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933"
)
EXPECTED_OBSERVATION_DATE = "2005-09-30"
EXPECTED_SOURCE_DEFINITION_VERSION = "0.1.0"
EXPECTED_SOURCE_ID = "uci_default_credit_card_clients"
CALIBRATION_BIN_COUNT = 10
METRIC_TOLERANCE = 1e-10
CALIBRATION_METRIC_TOLERANCE = 1e-6
LOG_LOSS_EPSILON = 1e-12
BLOCKER_CODES = frozenset({"time_direction_unavailable", "sensitivity_unavailable"})

STATIC_FEATURES = (
    "log_credit_limit",
    "age_years",
    "sex_code",
    "education_code",
    "marriage_code",
)
BEHAVIORAL_FEATURES = (
    "recent_max_delinquency",
    "delinquent_months_6m",
    "delinquency_deterioration",
    "latest_utilization_ratio",
    "payment_coverage_ratio",
    "zero_payment_streak",
    "recent_bill_growth",
)
COMBINED_FEATURES = (
    "log_credit_limit",
    "age_years",
    *BEHAVIORAL_FEATURES,
    "sex_code",
    "education_code",
    "marriage_code",
)
FEATURE_ALLOWLISTS = {
    "static": STATIC_FEATURES,
    "behavioral": BEHAVIORAL_FEATURES,
    "combined": COMBINED_FEATURES,
}
EXCLUDED_FEATURES = frozenset(
    {
        "customer_id",
        "next_month_default",
        "observation_date",
        "source_id",
        "source_file_sha256",
        "definition_version",
        "pipeline_run_id",
        "risk_points",
        "risk_band",
    }
)


@dataclass(frozen=True)
class ModelMetrics:
    """Independently calculated metrics for one test prediction set."""

    sample_count: int
    default_count: int
    default_rate: float
    average_pd: float
    roc_auc: float
    pr_auc: float
    brier_score: float
    log_loss: float
    expected_calibration_error_10_bin: float
    test_calibration_intercept: float
    test_calibration_slope: float
    calibration_bins: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Wave2ValidationReport:
    """Machine-readable validation result; not a human approval."""

    schema_version: str
    run_id: str | None
    definition_version: str | None
    generated_at: str
    status: str
    gate_4_eligible: bool
    issues: tuple[ValidationIssue, ...]
    checks: tuple[dict[str, Any], ...]
    recomputed_metrics: Mapping[str, Any]
    model_comparison: Mapping[str, Any]
    segment_stability: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "definition_version": self.definition_version,
            "generated_at": self.generated_at,
            "status": self.status,
            "gate_4_eligible": self.gate_4_eligible,
            "approval": "not_granted",
            "issues": [asdict(issue) for issue in self.issues],
            "checks": list(self.checks),
            "recomputed_metrics": dict(self.recomputed_metrics),
            "model_comparison": dict(self.model_comparison),
            "segment_stability": dict(self.segment_stability),
        }


def validate_wave2(
    artifact: object,
    *,
    generated_at: str | None = None,
    expected_population_count: int = EXPECTED_POPULATION_COUNT,
    metric_tolerance: float = METRIC_TOLERANCE,
    expected_default_count: int = EXPECTED_DEFAULT_COUNT,
    expected_source_run_id: str = EXPECTED_SOURCE_RUN_ID,
    expected_source_sha256: str = EXPECTED_SOURCE_SHA256,
) -> Wave2ValidationReport:
    """Validate the Wave 2 Builder artifact and independently recalculate it."""

    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    issues: list[ValidationIssue] = []
    checks: list[dict[str, Any]] = []
    recomputed: dict[str, Any] = {}
    comparisons: dict[str, Any] = {}
    segments: dict[str, Any] = {}

    if not isinstance(artifact, Mapping):
        _issue(issues, "artifact_not_object", "$", "artifact root must be an object")
        return _report(None, None, timestamp, issues, checks, recomputed, comparisons, segments)

    if artifact.get("schema_version") != "1.0":
        _issue(
            issues,
            "unsupported_schema_version",
            "$.schema_version",
            "schema_version must equal '1.0'",
        )
    if artifact.get("status") != "retrospective_internal_benchmark_only":
        _issue(
            issues,
            "artifact_status_mismatch",
            "$.status",
            "status must equal retrospective_internal_benchmark_only",
        )
    generated_value = artifact.get("generated_at")
    try:
        parsed_generated = (
            datetime.fromisoformat(generated_value.replace("Z", "+00:00"))
            if isinstance(generated_value, str)
            else None
        )
    except ValueError:
        parsed_generated = None
    if parsed_generated is None or parsed_generated.tzinfo is None:
        _issue(
            issues,
            "invalid_generated_at",
            "$.generated_at",
            "generated_at must be an ISO-8601 timestamp with timezone",
        )
    run_id = _required_text(artifact, "model_run_id", "$", issues)
    alias_run_id = _required_text(artifact, "run_id", "$", issues)
    definition_version = _required_text(
        artifact, "model_definition_version", "$", issues
    )
    alias_definition = _required_text(artifact, "definition_version", "$", issues)
    if run_id is not None and alias_run_id is not None and run_id != alias_run_id:
        _issue(
            issues,
            "run_id_mismatch",
            "$.run_id",
            "run_id must equal model_run_id",
        )
    if (
        definition_version is not None
        and alias_definition is not None
        and definition_version != alias_definition
    ):
        _issue(
            issues,
            "definition_version_mismatch",
            "$.definition_version",
            "definition_version must equal model_definition_version",
        )

    _validate_source_linkage(
        artifact,
        issues,
        expected_source_run_id=expected_source_run_id,
        expected_source_sha256=expected_source_sha256,
        expected_population_count=expected_population_count,
        expected_default_count=expected_default_count,
    )
    _record_check(
        checks,
        "source_run_hash_and_population_linkage",
        not any(
            issue.code
            in {
                "source_run_id_mismatch",
                "source_hash_mismatch",
                "source_metadata_not_object",
                "source_metadata_mismatch",
            }
            for issue in issues
        ),
        {
            "source_run_id": expected_source_run_id,
            "source_sha256": expected_source_sha256,
            "expected_borrowers": expected_population_count,
            "expected_defaults": expected_default_count,
        },
    )

    population, population_by_id, split_ids = _validate_population(
        artifact.get("population"),
        issues,
        expected_population_count=expected_population_count,
        expected_default_count=expected_default_count,
    )
    _record_check(
        checks,
        "population_and_split_integrity",
        not any(
            issue.code
            in {
                "population_not_list",
                "population_count_mismatch",
                "population_default_count_mismatch",
                "invalid_population_row",
                "duplicate_population_id",
                "invalid_split",
                "empty_split",
                "split_not_exhaustive",
                "split_overlap",
                "split_single_class",
                "split_thresholds_not_object",
                "split_threshold_mismatch",
                "cryptographic_split_mismatch",
                "split_counts_not_object",
                "split_count_mismatch",
            }
            for issue in issues
        ),
        {
            "population_count": len(population),
            "expected_population_count": expected_population_count,
            "split_counts": {name: len(ids) for name, ids in split_ids.items()},
        },
    )

    design = artifact.get("validation_design")
    temporal_eligible = _validate_design(
        design,
        issues,
        population=population,
        split_ids=split_ids,
        expected_population_count=expected_population_count,
    )
    _record_check(
        checks,
        "time_direction",
        temporal_eligible,
        {
            "genuine_time_direction": (
                design.get("genuine_time_direction")
                if isinstance(design, Mapping)
                else None
            ),
            "temporal_gate_eligible": (
                design.get("temporal_gate_eligible")
                if isinstance(design, Mapping)
                else None
            ),
        },
        blocked=not temporal_eligible,
    )

    _validate_feature_controls(
        artifact.get("feature_controls"),
        artifact.get("leakage_controls"),
        issues,
        checks,
    )

    models = artifact.get("models")
    if not isinstance(models, Mapping):
        _issue(issues, "models_not_object", "$.models", "models must be an object")
        models = {}

    prediction_sets: dict[str, list[dict[str, Any]]] = {}
    metrics_by_model: dict[str, ModelMetrics] = {}
    segment_by_model: dict[str, list[dict[str, Any]]] = {}
    for model_name in MODEL_NAMES:
        model = models.get(model_name)
        model_path = f"$.models.{model_name}"
        if not isinstance(model, Mapping):
            _issue(
                issues,
                "missing_model",
                model_path,
                f"required model {model_name!r} is missing",
            )
            continue
        _validate_model_identity(
            model,
            model_path,
            run_id=run_id,
            definition_version=definition_version,
            issues=issues,
        )
        _validate_model_training_controls(
            model,
            model_path,
            model_name=model_name,
            split_ids=split_ids,
            issues=issues,
        )
        predictions = _validate_predictions(
            model.get("test_predictions"),
            model_path,
            population_by_id=population_by_id,
            expected_test_ids=split_ids["test"],
            issues=issues,
        )
        prediction_sets[model_name] = predictions
        if predictions:
            metric = _calculate_metrics(predictions, issues, model_path)
            if metric is not None:
                metrics_by_model[model_name] = metric
                recomputed[model_name] = metric.to_dict()
                _compare_reported_metrics(
                    model.get("metrics"),
                    metric,
                    model_path,
                    issues,
                    tolerance=metric_tolerance,
                )
                _validate_calibration_application(
                    model,
                    predictions,
                    model_path,
                    issues,
                    tolerance=CALIBRATION_METRIC_TOLERANCE,
                )
                model_segments = _calculate_segment_stability(
                    predictions, population_by_id
                )
                segment_by_model[model_name] = model_segments
                _compare_reported_segments(
                    model.get("segment_stability"),
                    model_segments,
                    model_path,
                    issues,
                    tolerance=metric_tolerance,
                )

    _validate_cross_model_rows(prediction_sets, issues)
    if len(metrics_by_model) == len(MODEL_NAMES):
        comparisons = _model_comparisons(metrics_by_model)
        _compare_reported_comparisons(
            artifact.get("comparison"),
            comparisons,
            issues,
            tolerance=metric_tolerance,
        )
    segments = segment_by_model
    _validate_component_scope(artifact.get("component_scope"), issues, checks)

    _record_check(
        checks,
        "prediction_population_reconciliation",
        not any(
            issue.code
            in {
                "predictions_not_list",
                "invalid_prediction_row",
                "duplicate_prediction_id",
                "prediction_not_in_population",
                "prediction_not_test",
                "prediction_outcome_mismatch",
                "prediction_coverage_mismatch",
                "cross_model_population_mismatch",
                "cross_model_outcome_mismatch",
            }
            for issue in issues
        ),
        {
            "expected_test_count": len(split_ids["test"]),
            "model_prediction_counts": {
                name: len(rows) for name, rows in prediction_sets.items()
            },
        },
    )
    _record_check(
        checks,
        "probability_bounds_and_duplicates",
        not any(
            issue.code
            in {
                "invalid_probability",
                "invalid_raw_probability",
                "calibration_application_mismatch",
                "duplicate_prediction_id",
                "invalid_actual_default",
            }
            for issue in issues
        ),
        {
            "bounds": "[0, 1]",
            "models_checked": sorted(prediction_sets),
        },
    )
    _record_check(
        checks,
        "independent_metric_recalculation",
        len(metrics_by_model) == len(MODEL_NAMES)
        and not any(
            issue.code
            in {
                "single_class_test_set",
                "reported_metric_missing",
                "reported_metric_mismatch",
                "invalid_reported_metric",
                "reported_metric_method_mismatch",
                "reported_metric_use_mismatch",
                "reported_comparison_not_object",
                "reported_comparison_missing",
                "reported_comparison_mismatch",
            }
            for issue in issues
        ),
        {
            "models_recomputed": sorted(metrics_by_model),
            "calibration_bin_count": CALIBRATION_BIN_COUNT,
            "metric_tolerance": metric_tolerance,
        },
    )
    _record_check(
        checks,
        "segment_stability",
        len(segment_by_model) == len(MODEL_NAMES)
        and not any(
            issue.code
            in {
                "segment_field_missing",
                "reported_segments_not_list",
                "reported_segment_duplicate",
                "reported_segment_coverage_mismatch",
                "reported_segment_metric_mismatch",
            }
            for issue in issues
        ),
        {
            "segment_fields": list(SEGMENT_FIELDS),
            "model_segment_counts": {
                name: len(rows) for name, rows in segment_by_model.items()
            },
        },
    )
    _record_check(
        checks,
        "model_run_version_consistency",
        not any(
            issue.code
            in {
                "missing_text",
                "run_id_mismatch",
                "definition_version_mismatch",
                "model_run_id_mismatch",
                "model_definition_version_mismatch",
            }
            for issue in issues
        ),
        {
            "model_run_id": run_id,
            "model_definition_version": definition_version,
            "models_checked": list(MODEL_NAMES),
        },
    )

    return _report(
        run_id,
        definition_version,
        timestamp,
        issues,
        checks,
        recomputed,
        comparisons,
        segments,
    )


def _report(
    run_id: str | None,
    definition_version: str | None,
    timestamp: str,
    issues: Sequence[ValidationIssue],
    checks: Sequence[dict[str, Any]],
    recomputed: Mapping[str, Any],
    comparisons: Mapping[str, Any],
    segments: Mapping[str, Any],
) -> Wave2ValidationReport:
    blockers = [issue for issue in issues if issue.code in BLOCKER_CODES]
    failures = [issue for issue in issues if issue.code not in BLOCKER_CODES]
    status = "fail" if failures else "blocked" if blockers else "pass"
    gate_4_eligible = status == "pass"
    return Wave2ValidationReport(
        schema_version="1.0",
        run_id=run_id,
        definition_version=definition_version,
        generated_at=timestamp,
        status=status,
        gate_4_eligible=gate_4_eligible,
        issues=tuple(issues),
        checks=tuple(checks),
        recomputed_metrics=dict(recomputed),
        model_comparison=dict(comparisons),
        segment_stability=dict(segments),
    )


def _validate_population(
    value: object,
    issues: list[ValidationIssue],
    *,
    expected_population_count: int,
    expected_default_count: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, set[str]]]:
    if not isinstance(value, list):
        _issue(
            issues,
            "population_not_list",
            "$.population",
            "population must be a list of split assignments",
        )
        return [], {}, {name: set() for name in SPLIT_NAMES}
    if len(value) != expected_population_count:
        _issue(
            issues,
            "population_count_mismatch",
            "$.population",
            f"population has {len(value)} rows; expected {expected_population_count}",
        )
    raw_default_count = sum(
        int(item.get("actual_default") == 1)
        for item in value
        if isinstance(item, Mapping)
    )
    if raw_default_count != expected_default_count:
        _issue(
            issues,
            "population_default_count_mismatch",
            "$.population",
            f"population has {raw_default_count} defaults; expected {expected_default_count}",
        )
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    split_ids = {name: set() for name in SPLIT_NAMES}
    for index, item in enumerate(value):
        path = f"$.population[{index}]"
        if not isinstance(item, Mapping):
            _issue(issues, "invalid_population_row", path, "row must be an object")
            continue
        borrower_id = _identifier(item.get("borrower_id"))
        actual = item.get("actual_default")
        split = item.get("split")
        valid = True
        if borrower_id is None:
            _issue(
                issues,
                "invalid_population_row",
                f"{path}.borrower_id",
                "borrower_id must be a non-blank string or integer",
            )
            valid = False
        elif borrower_id in by_id:
            _issue(
                issues,
                "duplicate_population_id",
                f"{path}.borrower_id",
                f"borrower_id {borrower_id!r} appears more than once",
            )
            valid = False
        if actual not in (0, 1) or isinstance(actual, bool):
            _issue(
                issues,
                "invalid_actual_default",
                f"{path}.actual_default",
                "actual_default must be integer 0 or 1",
            )
            valid = False
        if split not in SPLIT_NAMES:
            _issue(
                issues,
                "invalid_split",
                f"{path}.split",
                f"split must be one of {list(SPLIT_NAMES)}",
            )
            valid = False
        for field in SEGMENT_FIELDS:
            if item.get(field) is None or (
                isinstance(item.get(field), str) and not item.get(field).strip()
            ):
                _issue(
                    issues,
                    "segment_field_missing",
                    f"{path}.{field}",
                    f"population row requires {field}",
                )
                valid = False
        if valid and borrower_id is not None:
            row = dict(item)
            row["borrower_id"] = borrower_id
            rows.append(row)
            by_id[borrower_id] = row
            split_ids[str(split)].add(borrower_id)
    for split, ids in split_ids.items():
        if not ids:
            _issue(
                issues,
                "empty_split",
                "$.population",
                f"split {split!r} has no borrowers",
            )
    union = set().union(*split_ids.values())
    if union != set(by_id):
        _issue(
            issues,
            "split_not_exhaustive",
            "$.population",
            "train/calibration/test split assignments do not exhaust unique population",
        )
    if any(
        split_ids[left] & split_ids[right]
        for left, right in (("train", "calibration"), ("train", "test"), ("calibration", "test"))
    ):
        _issue(
            issues,
            "split_overlap",
            "$.population",
            "train/calibration/test borrower sets must be pairwise disjoint",
        )
    for split in SPLIT_NAMES:
        outcomes = {
            int(by_id[identifier]["actual_default"]) for identifier in split_ids[split]
        }
        if outcomes != {0, 1}:
            _issue(
                issues,
                "split_single_class",
                "$.population",
                f"split {split!r} must contain both outcome classes",
            )
    return rows, by_id, split_ids


def _validate_design(
    value: object,
    issues: list[ValidationIssue],
    *,
    population: Sequence[Mapping[str, Any]],
    split_ids: Mapping[str, set[str]],
    expected_population_count: int,
) -> bool:
    if not isinstance(value, Mapping):
        _issue(
            issues,
            "validation_design_not_object",
            "$.validation_design",
            "validation_design must be an object",
        )
        return False
    for field in (
        "strategy",
        "split_key",
        "reason",
        "split_version",
        "split_algorithm",
        "split_input_contract",
        "split_order",
    ):
        _required_text(value, field, "$.validation_design", issues)
    fractions: list[float] = []
    for field in ("train_fraction", "calibration_fraction", "test_fraction"):
        item = value.get(field)
        if not _finite_number(item) or not 0 < float(item) < 1:
            _issue(
                issues,
                "invalid_split_fraction",
                f"$.validation_design.{field}",
                f"{field} must be a finite number strictly between zero and one",
            )
        else:
            fractions.append(float(item))
    if len(fractions) == 3 and not math.isclose(
        sum(fractions), 1.0, rel_tol=0.0, abs_tol=1e-12
    ):
        _issue(
            issues,
            "split_fraction_sum",
            "$.validation_design",
            "train/calibration/test fractions must sum to one",
        )
    if value.get("split_key") != "customer_id":
        _issue(
            issues,
            "split_key_mismatch",
            "$.validation_design.split_key",
            "approved split_key must equal 'customer_id'",
        )
    if value.get("split_algorithm") != "sha256_rank":
        _issue(
            issues,
            "split_algorithm_mismatch",
            "$.validation_design.split_algorithm",
            "approved split_algorithm must equal 'sha256_rank'",
        )
    if (
        value.get("split_input_contract")
        != "UTF-8 bytes of split_version + ':' + base-10 integer borrower_id"
    ):
        _issue(
            issues,
            "split_input_contract_mismatch",
            "$.validation_design.split_input_contract",
            "split input contract does not match the approved SHA-256 definition",
        )
    if value.get("split_order") != "ascending_full_hex_digest_then_borrower_id":
        _issue(
            issues,
            "split_order_mismatch",
            "$.validation_design.split_order",
            "split order does not match the approved deterministic rank definition",
        )
    _recompute_hash_split(
        value,
        population,
        split_ids,
        issues,
        expected_population_count=expected_population_count,
    )
    genuine = value.get("genuine_time_direction")
    eligible = value.get("temporal_gate_eligible")
    if not isinstance(genuine, bool) or not isinstance(eligible, bool):
        _issue(
            issues,
            "invalid_temporal_flags",
            "$.validation_design",
            "genuine_time_direction and temporal_gate_eligible must be booleans",
        )
        return False
    if genuine != eligible:
        _issue(
            issues,
            "temporal_flag_mismatch",
            "$.validation_design",
            "temporal_gate_eligible must equal genuine_time_direction",
        )
        return False
    if not genuine:
        _issue(
            issues,
            "time_direction_unavailable",
            "$.validation_design.genuine_time_direction",
            "Gate 4 is blocked: the source has no borrower-level observation timestamp, "
            "so a stable ID split is not genuine time-direction validation",
        )
        return False
    train_end = _required_text(value, "train_observation_end", "$.validation_design", issues)
    test_start = _required_text(
        value, "test_observation_start", "$.validation_design", issues
    )
    if train_end is not None and test_start is not None and train_end >= test_start:
        _issue(
            issues,
            "temporal_order_invalid",
            "$.validation_design",
            "train_observation_end must precede test_observation_start",
        )
        return False
    return True


def _validate_source_linkage(
    artifact: Mapping[str, Any],
    issues: list[ValidationIssue],
    *,
    expected_source_run_id: str,
    expected_source_sha256: str,
    expected_population_count: int,
    expected_default_count: int,
) -> None:
    source_run_id = artifact.get("source_run_id")
    if source_run_id != expected_source_run_id:
        _issue(
            issues,
            "source_run_id_mismatch",
            "$.source_run_id",
            f"source_run_id must equal validated Wave 1 run {expected_source_run_id!r}",
        )
    source_sha256 = artifact.get("source_sha256")
    if source_sha256 != expected_source_sha256:
        _issue(
            issues,
            "source_hash_mismatch",
            "$.source_sha256",
            "source_sha256 does not match the registered official XLS hash",
        )
    metadata = artifact.get("source_metadata")
    if not isinstance(metadata, Mapping):
        _issue(
            issues,
            "source_metadata_not_object",
            "$.source_metadata",
            "source_metadata must be an object",
        )
        return
    expected = {
        "source_id": EXPECTED_SOURCE_ID,
        "source_file_sha256": expected_source_sha256,
        "source_definition_version": EXPECTED_SOURCE_DEFINITION_VERSION,
        "observation_date": EXPECTED_OBSERVATION_DATE,
        "borrower_count": expected_population_count,
        "observed_default_count": expected_default_count,
    }
    for key, required in expected.items():
        if metadata.get(key) != required:
            _issue(
                issues,
                "source_metadata_mismatch",
                f"$.source_metadata.{key}",
                f"{key} must equal validated source value {required!r}",
            )


def _recompute_hash_split(
    design: Mapping[str, Any],
    population: Sequence[Mapping[str, Any]],
    split_ids: Mapping[str, set[str]],
    issues: list[ValidationIssue],
    *,
    expected_population_count: int,
) -> None:
    thresholds = design.get("split_thresholds")
    if not isinstance(thresholds, Mapping):
        _issue(
            issues,
            "split_thresholds_not_object",
            "$.validation_design.split_thresholds",
            "split_thresholds must be an object",
        )
        return
    train_end = int(expected_population_count * 0.60)
    calibration_end = int(expected_population_count * 0.80)
    expected_thresholds = {
        "train_rank_end_exclusive": train_end,
        "calibration_rank_end_exclusive": calibration_end,
        "population_size": expected_population_count,
    }
    for key, expected in expected_thresholds.items():
        if thresholds.get(key) != expected:
            _issue(
                issues,
                "split_threshold_mismatch",
                f"$.validation_design.split_thresholds.{key}",
                f"{key} must equal {expected}",
            )
    split_version = design.get("split_version")
    if not isinstance(split_version, str) or not split_version:
        return
    ranked: list[tuple[bytes, int, str]] = []
    for row in population:
        identifier = str(row["borrower_id"])
        try:
            integer_id = int(identifier)
        except ValueError:
            _issue(
                issues,
                "split_identifier_not_integer",
                "$.population",
                "approved split requires integer borrower IDs",
            )
            return
        digest = hashlib.sha256(f"{split_version}:{integer_id}".encode("utf-8")).digest()
        ranked.append((digest, integer_id, identifier))
    ranked.sort(key=lambda item: (item[0], item[1]))
    reconstructed = {name: set() for name in SPLIT_NAMES}
    for rank, (_, _, identifier) in enumerate(ranked):
        split = (
            "train"
            if rank < train_end
            else "calibration"
            if rank < calibration_end
            else "test"
        )
        reconstructed[split].add(identifier)
    for split in SPLIT_NAMES:
        if reconstructed[split] != split_ids[split]:
            _issue(
                issues,
                "cryptographic_split_mismatch",
                "$.population",
                f"{split} assignments do not match independent SHA-256 rank split",
            )
    reported_counts = design.get("split_counts")
    if not isinstance(reported_counts, Mapping):
        _issue(
            issues,
            "split_counts_not_object",
            "$.validation_design.split_counts",
            "split_counts must be an object",
        )
    else:
        for split in SPLIT_NAMES:
            if reported_counts.get(split) != len(split_ids[split]):
                _issue(
                    issues,
                    "split_count_mismatch",
                    f"$.validation_design.split_counts.{split}",
                    f"reported {split} count does not match reconstructed split",
                )


def _validate_feature_controls(
    value: object,
    leakage: object,
    issues: list[ValidationIssue],
    checks: list[dict[str, Any]],
) -> None:
    start = len(issues)
    if not isinstance(value, Mapping):
        _issue(
            issues,
            "feature_controls_not_object",
            "$.feature_controls",
            "feature_controls must be an object",
        )
    else:
        allowlists = value.get("allowlists")
        if not isinstance(allowlists, Mapping):
            _issue(
                issues,
                "feature_allowlists_not_object",
                "$.feature_controls.allowlists",
                "feature allowlists must be an object",
            )
        else:
            for model_name, expected in FEATURE_ALLOWLISTS.items():
                declared = allowlists.get(model_name)
                if not isinstance(declared, list) or tuple(declared) != expected:
                    _issue(
                        issues,
                        "feature_allowlist_mismatch",
                        f"$.feature_controls.allowlists.{model_name}",
                        f"{model_name} allowlist does not match approved version",
                    )
        excluded = value.get("excluded_features")
        if not isinstance(excluded, list) or frozenset(excluded) != EXCLUDED_FEATURES:
            _issue(
                issues,
                "excluded_features_mismatch",
                "$.feature_controls.excluded_features",
                "excluded feature set does not match the approved version",
            )
        if value.get("preprocessing_fit_split") != "train":
            _issue(
                issues,
                "preprocessing_fit_split_mismatch",
                "$.feature_controls.preprocessing_fit_split",
                "preprocessing must be fitted on train",
            )
        if value.get("calibration_fit_split") != "calibration":
            _issue(
                issues,
                "calibration_fit_split_mismatch",
                "$.feature_controls.calibration_fit_split",
                "calibration must be fitted on calibration",
            )
    if not isinstance(leakage, Mapping):
        _issue(
            issues,
            "leakage_controls_not_object",
            "$.leakage_controls",
            "leakage_controls must be an object",
        )
    else:
        if leakage.get("outcome_field") != "next_month_default":
            _issue(
                issues,
                "outcome_field_mismatch",
                "$.leakage_controls.outcome_field",
                "outcome_field must equal next_month_default",
            )
        forbidden = leakage.get("forbidden_features")
        if not isinstance(forbidden, list) or frozenset(forbidden) != EXCLUDED_FEATURES:
            _issue(
                issues,
                "forbidden_features_mismatch",
                "$.leakage_controls.forbidden_features",
                "forbidden feature set does not match the approved version",
            )
        if (
            leakage.get("feature_timing_status")
            != "wave1_gate3_passed_but_single_observation_date"
        ):
            _issue(
                issues,
                "feature_timing_status_mismatch",
                "$.leakage_controls.feature_timing_status",
                "feature timing status must preserve the single-date limitation",
            )
        required_checks = {
            "explicit_allowlist_features_only",
            "target_not_in_feature_matrix",
            "identifiers_dates_run_source_metadata_excluded",
            "risk_points_and_risk_band_excluded",
            "preprocessing_fit_on_train_only",
            "calibration_fit_on_calibration_only",
            "test_used_for_final_evaluation_only",
        }
        declared_checks = leakage.get("checks")
        if not isinstance(declared_checks, list) or set(declared_checks) != required_checks:
            _issue(
                issues,
                "leakage_checks_mismatch",
                "$.leakage_controls.checks",
                "declared leakage checks do not match the approved fixed set",
            )
    _record_check(
        checks,
        "observation_timing_and_leakage",
        len(issues) == start,
        {
            "allowlists": "$.feature_controls.allowlists",
            "exclusions": "$.feature_controls.excluded_features",
            "leakage_controls": "$.leakage_controls",
        },
    )


def _validate_model_identity(
    model: Mapping[str, Any],
    path: str,
    *,
    run_id: str | None,
    definition_version: str | None,
    issues: list[ValidationIssue],
) -> None:
    model_run_id = _required_text(model, "model_run_id", path, issues)
    model_version = _required_text(model, "model_definition_version", path, issues)
    if run_id is not None and model_run_id is not None and model_run_id != run_id:
        _issue(
            issues,
            "model_run_id_mismatch",
            f"{path}.model_run_id",
            f"model run ID does not match top-level model_run_id {run_id!r}",
        )
    if (
        definition_version is not None
        and model_version is not None
        and model_version != definition_version
    ):
        _issue(
            issues,
            "model_definition_version_mismatch",
            f"{path}.model_definition_version",
            "model definition version does not match top-level version",
        )


def _validate_model_training_controls(
    model: Mapping[str, Any],
    path: str,
    *,
    model_name: str,
    split_ids: Mapping[str, set[str]],
    issues: list[ValidationIssue],
) -> None:
    features = model.get("feature_names")
    if not isinstance(features, list) or tuple(features) != FEATURE_ALLOWLISTS[model_name]:
        _issue(
            issues,
            "model_feature_allowlist_mismatch",
            f"{path}.feature_names",
            f"{model_name} model features do not match the approved fixed allowlist",
        )
    fit_counts = model.get("fit_counts")
    if not isinstance(fit_counts, Mapping):
        _issue(
            issues,
            "fit_counts_not_object",
            f"{path}.fit_counts",
            "fit_counts must be an object",
        )
    else:
        for split in SPLIT_NAMES:
            if fit_counts.get(split) != len(split_ids[split]):
                _issue(
                    issues,
                    "fit_count_mismatch",
                    f"{path}.fit_counts.{split}",
                    f"{split} fit count must equal reconstructed split count",
                )
    preprocessing = model.get("preprocessing")
    if not isinstance(preprocessing, Mapping) or preprocessing.get("fit_population") != (
        "train_only"
    ):
        _issue(
            issues,
            "preprocessing_population_mismatch",
            f"{path}.preprocessing.fit_population",
            "preprocessing fit population must equal train_only",
        )
    calibration = model.get("calibration")
    if not isinstance(calibration, Mapping):
        _issue(
            issues,
            "calibration_not_object",
            f"{path}.calibration",
            "calibration metadata must be an object",
        )
    else:
        if calibration.get("fit_population") != "calibration_only":
            _issue(
                issues,
                "calibration_population_mismatch",
                f"{path}.calibration.fit_population",
                "calibrator fit population must equal calibration_only",
            )
        if calibration.get("method") != "platt_on_disjoint_calibration":
            _issue(
                issues,
                "calibration_method_mismatch",
                f"{path}.calibration.method",
                "calibration method must equal platt_on_disjoint_calibration",
            )
        for field in ("platt_fit_slope", "platt_fit_intercept"):
            if not _finite_number(calibration.get(field)):
                _issue(
                    issues,
                    "invalid_calibration_parameter",
                    f"{path}.calibration.{field}",
                    f"calibration {field} must be finite",
                )


def _validate_calibration_application(
    model: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    path: str,
    issues: list[ValidationIssue],
    *,
    tolerance: float,
) -> None:
    calibration = model.get("calibration")
    if not isinstance(calibration, Mapping):
        return
    slope = calibration.get("platt_fit_slope")
    intercept = calibration.get("platt_fit_intercept")
    if not _finite_number(slope) or not _finite_number(intercept):
        return
    for index, row in enumerate(rows):
        raw_pd = row.get("raw_pd")
        if not _finite_number(raw_pd) or not 0 <= float(raw_pd) <= 1:
            _issue(
                issues,
                "invalid_raw_probability",
                f"{path}.test_predictions[{index}].raw_pd",
                "raw_pd must be a finite probability in [0, 1]",
            )
            continue
        clipped = min(max(float(raw_pd), LOG_LOSS_EPSILON), 1 - LOG_LOSS_EPSILON)
        logit = math.log(clipped / (1 - clipped))
        linear = float(intercept) + float(slope) * logit
        expected = (
            1.0 / (1.0 + math.exp(-linear))
            if linear >= 0
            else math.exp(linear) / (1.0 + math.exp(linear))
        )
        if not math.isclose(
            expected,
            float(row["predicted_pd"]),
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            _issue(
                issues,
                "calibration_application_mismatch",
                f"{path}.test_predictions[{index}].predicted_pd",
                "predicted_pd does not reconcile to raw_pd and saved Platt parameters",
            )
            break


def _validate_component_scope(
    value: object,
    issues: list[ValidationIssue],
    checks: list[dict[str, Any]],
) -> None:
    start = len(issues)
    if not isinstance(value, Mapping):
        _issue(
            issues,
            "component_scope_not_object",
            "$.component_scope",
            "component_scope must be an object",
        )
    else:
        pd = value.get("pd")
        if (
            not isinstance(pd, Mapping)
            or pd.get("status") != "prototype_retrospective_internal_benchmark"
        ):
            _issue(
                issues,
                "pd_scope_mismatch",
                "$.component_scope.pd",
                "PD must be explicitly labeled prototype_retrospective_internal_benchmark",
            )
        for component in ("stage", "ead", "lgd", "ecl"):
            item = value.get(component)
            if not isinstance(item, Mapping) or item.get("status") != "not_estimated":
                _issue(
                    issues,
                    "unsupported_component_claim",
                    f"$.component_scope.{component}",
                    f"{component.upper()} must be explicitly labeled not_estimated",
                )
        sensitivity = value.get("scenario_sensitivity")
        if not isinstance(sensitivity, Mapping) or sensitivity.get("status") not in {
            "not_estimated",
            "deferred",
        }:
            _issue(
                issues,
                "sensitivity_scope_mismatch",
                "$.component_scope.scenario_sensitivity",
                "scenario sensitivity must be explicitly deferred or not_estimated",
            )
        else:
            _issue(
                issues,
                "sensitivity_unavailable",
                "$.component_scope.scenario_sensitivity",
                "Gate 4 sensitivity-direction evidence is unavailable; no approved "
                "scenario or behavioral shock values are present",
            )
    _record_check(
        checks,
        "proxy_labels_and_component_scope",
        len([issue for issue in issues[start:] if issue.code != "sensitivity_unavailable"])
        == 0,
        {"required_not_estimated": ["stage", "ead", "lgd", "ecl"]},
    )


def _validate_predictions(
    value: object,
    model_path: str,
    *,
    population_by_id: Mapping[str, Mapping[str, Any]],
    expected_test_ids: set[str],
    issues: list[ValidationIssue],
) -> list[dict[str, Any]]:
    path = f"{model_path}.test_predictions"
    if not isinstance(value, list):
        _issue(issues, "predictions_not_list", path, "test_predictions must be a list")
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        row_path = f"{path}[{index}]"
        if not isinstance(item, Mapping):
            _issue(issues, "invalid_prediction_row", row_path, "row must be an object")
            continue
        borrower_id = _identifier(item.get("borrower_id"))
        actual = item.get("actual_default")
        probability = item.get("predicted_pd")
        split = item.get("split")
        valid = True
        if borrower_id is None:
            _issue(
                issues,
                "invalid_prediction_row",
                f"{row_path}.borrower_id",
                "borrower_id must be a non-blank string or integer",
            )
            valid = False
        elif borrower_id in seen:
            _issue(
                issues,
                "duplicate_prediction_id",
                f"{row_path}.borrower_id",
                f"borrower_id {borrower_id!r} appears more than once",
            )
            valid = False
        elif borrower_id not in population_by_id:
            _issue(
                issues,
                "prediction_not_in_population",
                f"{row_path}.borrower_id",
                f"borrower_id {borrower_id!r} is absent from population",
            )
            valid = False
        if actual not in (0, 1) or isinstance(actual, bool):
            _issue(
                issues,
                "invalid_actual_default",
                f"{row_path}.actual_default",
                "actual_default must be integer 0 or 1",
            )
            valid = False
        if not _finite_number(probability) or not 0 <= float(probability) <= 1:
            _issue(
                issues,
                "invalid_probability",
                f"{row_path}.predicted_pd",
                "predicted_pd must be a finite number in [0, 1]",
            )
            valid = False
        if split != "test":
            _issue(
                issues,
                "prediction_not_test",
                f"{row_path}.split",
                "all published model predictions in this artifact must have split 'test'",
            )
            valid = False
        if borrower_id is not None and borrower_id in population_by_id:
            population_row = population_by_id[borrower_id]
            if population_row.get("split") != "test":
                _issue(
                    issues,
                    "prediction_not_test",
                    f"{row_path}.borrower_id",
                    "prediction borrower is not assigned to the test split",
                )
                valid = False
            if actual in (0, 1) and actual != population_row.get("actual_default"):
                _issue(
                    issues,
                    "prediction_outcome_mismatch",
                    f"{row_path}.actual_default",
                    "prediction outcome does not match population outcome",
                )
                valid = False
        if valid and borrower_id is not None:
            row = dict(item)
            row["borrower_id"] = borrower_id
            row["predicted_pd"] = float(probability)
            rows.append(row)
            seen.add(borrower_id)
    if seen != expected_test_ids:
        missing = len(expected_test_ids - seen)
        extra = len(seen - expected_test_ids)
        _issue(
            issues,
            "prediction_coverage_mismatch",
            path,
            f"predictions must exactly cover test population; missing={missing}, extra={extra}",
        )
    return rows


def _calculate_metrics(
    rows: Sequence[Mapping[str, Any]],
    issues: list[ValidationIssue],
    model_path: str,
) -> ModelMetrics | None:
    labels = [int(row["actual_default"]) for row in rows]
    probabilities = [float(row["predicted_pd"]) for row in rows]
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        _issue(
            issues,
            "single_class_test_set",
            f"{model_path}.test_predictions",
            "ROC AUC requires both target classes in the test population",
        )
        return None
    auc = _roc_auc(labels, probabilities)
    pr_auc = _average_precision(labels, probabilities)
    brier = sum((p - y) ** 2 for y, p in zip(labels, probabilities, strict=True)) / len(
        labels
    )
    log_loss = -sum(
        y * math.log(min(max(p, LOG_LOSS_EPSILON), 1 - LOG_LOSS_EPSILON))
        + (1 - y)
        * math.log(min(max(1 - p, LOG_LOSS_EPSILON), 1 - LOG_LOSS_EPSILON))
        for y, p in zip(labels, probabilities, strict=True)
    ) / len(labels)
    bins = _calibration_bins(labels, probabilities)
    ece = sum(
        bucket["sample_count"]
        / len(labels)
        * abs(bucket["average_pd"] - bucket["observed_default_rate"])
        for bucket in bins
    )
    try:
        calibration_intercept, calibration_slope = _test_calibration_fit(
            labels, probabilities
        )
    except ValueError as exc:
        _issue(
            issues,
            "test_calibration_fit_failure",
            f"{model_path}.test_predictions",
            str(exc),
        )
        return None
    return ModelMetrics(
        sample_count=len(labels),
        default_count=positives,
        default_rate=positives / len(labels),
        average_pd=sum(probabilities) / len(probabilities),
        roc_auc=auc,
        pr_auc=pr_auc,
        brier_score=brier,
        log_loss=log_loss,
        expected_calibration_error_10_bin=ece,
        test_calibration_intercept=calibration_intercept,
        test_calibration_slope=calibration_slope,
        calibration_bins=tuple(bins),
    )


def _roc_auc(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    ordered = sorted(zip(probabilities, labels, strict=True), key=lambda item: item[0])
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    positives = sum(labels)
    negatives = len(labels) - positives
    return (
        positive_rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)


def _average_precision(
    labels: Sequence[int], probabilities: Sequence[float]
) -> float:
    """Match the non-interpolated average precision definition."""

    grouped: dict[float, list[int]] = {}
    for label, probability in zip(labels, probabilities, strict=True):
        grouped.setdefault(probability, []).append(label)
    true_positives = 0
    false_positives = 0
    previous_recall = 0.0
    area = 0.0
    positives = sum(labels)
    for probability in sorted(grouped, reverse=True):
        group = grouped[probability]
        true_positives += sum(group)
        false_positives += len(group) - sum(group)
        recall = true_positives / positives
        precision = true_positives / (true_positives + false_positives)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def _test_calibration_fit(
    labels: Sequence[int], probabilities: Sequence[float]
) -> tuple[float, float]:
    """Re-fit the declared diagnostic estimator from saved test predictions.

    This uses the project model dependency directly but does not import Builder
    code.  The fixed weak L2 penalty is part of the declared diagnostic
    definition, so an unpenalized Newton fit would be a different metric.
    """

    logits = [
        math.log(
            min(max(probability, LOG_LOSS_EPSILON), 1 - LOG_LOSS_EPSILON)
            / (1 - min(max(probability, LOG_LOSS_EPSILON), 1 - LOG_LOSS_EPSILON))
        )
        for probability in probabilities
    ]
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:  # pragma: no cover - Wave 2 dependency preflight
        raise ValueError(
            "Wave 2 model dependencies are required for calibration diagnostics"
        ) from exc
    diagnostic = LogisticRegression(
        C=1e6,
        solver="lbfgs",
        max_iter=2_000,
        random_state=20260727,
    )
    diagnostic.fit(np.asarray(logits, dtype=float).reshape(-1, 1), np.asarray(labels))
    return float(diagnostic.intercept_[0]), float(diagnostic.coef_[0][0])


def _calibration_bins(
    labels: Sequence[int], probabilities: Sequence[float]
) -> list[dict[str, Any]]:
    grouped: list[list[tuple[int, float]]] = [[] for _ in range(CALIBRATION_BIN_COUNT)]
    for label, probability in zip(labels, probabilities, strict=True):
        index = min(int(probability * CALIBRATION_BIN_COUNT), CALIBRATION_BIN_COUNT - 1)
        grouped[index].append((label, probability))
    result: list[dict[str, Any]] = []
    for index, values in enumerate(grouped):
        if not values:
            continue
        sample_count = len(values)
        default_count = sum(label for label, _ in values)
        result.append(
            {
                "bin": index + 1,
                "lower_bound": index / CALIBRATION_BIN_COUNT,
                "upper_bound": (index + 1) / CALIBRATION_BIN_COUNT,
                "sample_count": sample_count,
                "default_count": default_count,
                "average_pd": sum(probability for _, probability in values)
                / sample_count,
                "observed_default_rate": default_count / sample_count,
            }
        )
    return result


def _compare_reported_metrics(
    value: object,
    calculated: ModelMetrics,
    model_path: str,
    issues: list[ValidationIssue],
    *,
    tolerance: float,
) -> None:
    test_metrics: object = None
    if isinstance(value, Mapping):
        test_metrics = value.get("test")
    if not isinstance(test_metrics, Mapping):
        _issue(
            issues,
            "reported_metric_missing",
            f"{model_path}.metrics.test",
            "reported test metrics must be an object",
        )
        return
    expected = {
        "sample_count": calculated.sample_count,
        "default_count": calculated.default_count,
        "default_rate": calculated.default_rate,
        "average_pd": calculated.average_pd,
        "roc_auc": calculated.roc_auc,
        "pr_auc": calculated.pr_auc,
        "brier_score": calculated.brier_score,
        "log_loss": calculated.log_loss,
        "expected_calibration_error_10_bin": (
            calculated.expected_calibration_error_10_bin
        ),
        "calibration_intercept": calculated.test_calibration_intercept,
        "calibration_slope": calculated.test_calibration_slope,
    }
    if test_metrics.get("method") != "descriptive_logistic_actual_on_logit_predicted":
        _issue(
            issues,
            "reported_metric_method_mismatch",
            f"{model_path}.metrics.test.method",
            "test calibration diagnostic method does not match the approved definition",
        )
    if test_metrics.get("use") != "diagnostic_only_not_refit":
        _issue(
            issues,
            "reported_metric_use_mismatch",
            f"{model_path}.metrics.test.use",
            "test calibration diagnostic must be labeled diagnostic_only_not_refit",
        )
    for name, actual in expected.items():
        reported = test_metrics.get(name)
        path = f"{model_path}.metrics.test.{name}"
        if not _finite_number(reported):
            _issue(
                issues,
                "invalid_reported_metric",
                path,
                f"reported {name} must be a finite number",
            )
            continue
        field_tolerance = (
            CALIBRATION_METRIC_TOLERANCE
            if name in {"calibration_intercept", "calibration_slope"}
            else tolerance
        )
        if not math.isclose(
            float(reported), float(actual), rel_tol=0.0, abs_tol=field_tolerance
        ):
            _issue(
                issues,
                "reported_metric_mismatch",
                path,
                f"reported {reported!r} does not match independent value {actual!r}",
            )


def _calculate_segment_stability(
    rows: Sequence[Mapping[str, Any]],
    population_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field in SEGMENT_FIELDS:
        grouped: dict[str, list[tuple[int, float]]] = {}
        for row in rows:
            source_row = population_by_id[str(row["borrower_id"])]
            value = str(source_row[field])
            grouped.setdefault(value, []).append(
                (int(row["actual_default"]), float(row["predicted_pd"]))
            )
        for value in sorted(grouped):
            observations = grouped[value]
            count = len(observations)
            defaults = sum(label for label, _ in observations)
            result.append(
                {
                    "segment_field": field,
                    "segment_value": value,
                    "sample_count": count,
                    "default_count": defaults,
                    "default_rate": defaults / count,
                    "average_pd": sum(pd for _, pd in observations) / count,
                    "brier_score": sum(
                        (pd - label) ** 2 for label, pd in observations
                    )
                    / count,
                }
            )
    return result


def _compare_reported_segments(
    value: object,
    calculated: Sequence[Mapping[str, Any]],
    model_path: str,
    issues: list[ValidationIssue],
    *,
    tolerance: float,
) -> None:
    path = f"{model_path}.segment_stability"
    if not isinstance(value, list):
        _issue(
            issues,
            "reported_segments_not_list",
            path,
            "segment_stability must be a list",
        )
        return
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            _issue(
                issues,
                "reported_segments_not_list",
                f"{path}[{index}]",
                "segment row must be an object",
            )
            continue
        key = (str(row.get("segment_field")), str(row.get("segment_value")))
        if key in indexed:
            _issue(
                issues,
                "reported_segment_duplicate",
                f"{path}[{index}]",
                f"duplicate segment key {key!r}",
            )
        indexed[key] = row
    expected = {
        (str(row["segment_field"]), str(row["segment_value"])): row
        for row in calculated
    }
    if set(indexed) != set(expected):
        _issue(
            issues,
            "reported_segment_coverage_mismatch",
            path,
            "reported segment keys do not match independently reconstructed keys",
        )
    for key in sorted(set(indexed) & set(expected)):
        for field in (
            "sample_count",
            "default_count",
            "default_rate",
            "average_pd",
            "brier_score",
        ):
            reported = indexed[key].get(field)
            actual = expected[key][field]
            if not _finite_number(reported) or not math.isclose(
                float(reported), float(actual), rel_tol=0.0, abs_tol=tolerance
            ):
                _issue(
                    issues,
                    "reported_segment_metric_mismatch",
                    path,
                    f"segment {key!r} field {field} does not match independent value",
                )


def _validate_cross_model_rows(
    prediction_sets: Mapping[str, Sequence[Mapping[str, Any]]],
    issues: list[ValidationIssue],
) -> None:
    if not all(name in prediction_sets for name in MODEL_NAMES):
        return
    reference = {
        str(row["borrower_id"]): int(row["actual_default"])
        for row in prediction_sets["static"]
    }
    for model_name in MODEL_NAMES[1:]:
        candidate = {
            str(row["borrower_id"]): int(row["actual_default"])
            for row in prediction_sets[model_name]
        }
        if set(candidate) != set(reference):
            _issue(
                issues,
                "cross_model_population_mismatch",
                f"$.models.{model_name}.test_predictions",
                "all models must contain the same test borrower IDs",
            )
        elif candidate != reference:
            _issue(
                issues,
                "cross_model_outcome_mismatch",
                f"$.models.{model_name}.test_predictions",
                "all models must contain the same outcomes per test borrower",
            )


def _model_comparisons(metrics: Mapping[str, ModelMetrics]) -> dict[str, Any]:
    pairs = (
        ("behavioral_minus_static", "behavioral", "static"),
        ("combined_minus_static", "combined", "static"),
        ("combined_minus_behavioral", "combined", "behavioral"),
    )
    result: dict[str, Any] = {}
    for label, left, right in pairs:
        result[label] = {
            "roc_auc_difference": metrics[left].roc_auc - metrics[right].roc_auc,
            "pr_auc_difference": metrics[left].pr_auc - metrics[right].pr_auc,
            "brier_score_difference": (
                metrics[left].brier_score - metrics[right].brier_score
            ),
            "log_loss_difference": metrics[left].log_loss - metrics[right].log_loss,
            "ece_difference": (
                metrics[left].expected_calibration_error_10_bin
                - metrics[right].expected_calibration_error_10_bin
            ),
        }
    return result


def _compare_reported_comparisons(
    value: object,
    calculated: Mapping[str, Any],
    issues: list[ValidationIssue],
    *,
    tolerance: float,
) -> None:
    if not isinstance(value, Mapping):
        _issue(
            issues,
            "reported_comparison_not_object",
            "$.comparison",
            "comparison must be an object",
        )
        return
    expected_by_model = {
        "static": {
            "test_roc_auc_delta_vs_static": 0.0,
            "test_pr_auc_delta_vs_static": 0.0,
            "test_brier_delta_vs_static": 0.0,
        },
        "behavioral": {
            "test_roc_auc_delta_vs_static": calculated["behavioral_minus_static"][
                "roc_auc_difference"
            ],
            "test_pr_auc_delta_vs_static": calculated["behavioral_minus_static"][
                "pr_auc_difference"
            ],
            "test_brier_delta_vs_static": calculated["behavioral_minus_static"][
                "brier_score_difference"
            ],
        },
        "combined": {
            "test_roc_auc_delta_vs_static": calculated["combined_minus_static"][
                "roc_auc_difference"
            ],
            "test_pr_auc_delta_vs_static": calculated["combined_minus_static"][
                "pr_auc_difference"
            ],
            "test_brier_delta_vs_static": calculated["combined_minus_static"][
                "brier_score_difference"
            ],
        },
    }
    for model_name, expected in expected_by_model.items():
        row = value.get(model_name)
        if not isinstance(row, Mapping):
            _issue(
                issues,
                "reported_comparison_missing",
                f"$.comparison.{model_name}",
                "model comparison row is required",
            )
            continue
        for field, actual in expected.items():
            reported = row.get(field)
            if not _finite_number(reported) or not math.isclose(
                float(reported), float(actual), rel_tol=0.0, abs_tol=tolerance
            ):
                _issue(
                    issues,
                    "reported_comparison_mismatch",
                    f"$.comparison.{model_name}.{field}",
                    f"reported comparison does not match independent value {actual!r}",
                )


def _required_text(
    mapping: Mapping[str, Any],
    key: str,
    base_path: str,
    issues: list[ValidationIssue],
) -> str | None:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        _issue(
            issues,
            "missing_text",
            f"{base_path}.{key}",
            f"{key} must be a non-blank string",
        )
        return None
    return value


def _identifier(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _issue(
    issues: list[ValidationIssue], code: str, path: str, message: str
) -> None:
    issues.append(ValidationIssue(code, path, message))


def _record_check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    evidence: Mapping[str, Any],
    *,
    blocked: bool = False,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "pass" if passed else "blocked" if blocked else "fail",
            "evidence": dict(evidence),
        }
    )


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently validate a Wave 2 PD result artifact"
    )
    parser.add_argument("--input", type=Path, required=True, help="Builder JSON artifact")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New validation report path; existing files are never overwritten",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        artifact = load_json_object(args.input)
        report = validate_wave2(artifact)
        _write_new_json(args.output, report.to_dict())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Wave 2 validation blocked: {exc}")
        return 2
    print(
        f"Wave 2 validation {report.status}: run_id={report.run_id!r}, "
        f"issues={len(report.issues)}, gate_4_eligible={report.gate_4_eligible}"
    )
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
