"""Fit and report an explainable cross-sectional PD prototype.

Purpose:
    Compare static, behavioral, and combined logistic PD prototypes with a
    deterministic borrower split and independently recomputable test evidence.
Inputs:
    A run-scoped borrower frame extracted by
    ``sql/risk_components/100_pd_model_extract.sql``.
Outputs:
    A JSON-serializable model packet with population split membership, feature
    coefficients, calibration/test metrics, segment diagnostics, and row-level
    test predictions.
Observation point:
    All features must be available at the single borrower observation date.
    The next-month default field is outcome-only.
Key assumptions:
    The SHA-256 customer split is non-temporal. Preprocessing and logistic
    parameters use train rows only; Platt calibration uses the disjoint
    calibration rows only; test rows are held out until final evaluation.
Validation:
    Contract assertions fail closed on duplicate borrowers, invalid targets,
    inconsistent metadata, split overlap, leakage, non-finite probabilities,
    or population/prediction reconciliation errors. Independent validation must
    recompute the saved row-level metrics before any internal use.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


MODEL_DEFINITION_VERSION = "0.2.0"
SPLIT_VERSION = "customer_sha256_v1"
MODEL_NAMES = ("static", "behavioral", "combined")

OUTCOME_FIELD = "next_month_default"
IDENTIFIER_AND_METADATA_FIELDS = frozenset(
    {
        "customer_id",
        OUTCOME_FIELD,
        "observation_date",
        "source_id",
        "source_file_sha256",
        "definition_version",
        "pipeline_run_id",
        "risk_points",
        "risk_band",
    }
)
STATIC_NUMERIC = ("log_credit_limit", "age_years")
STATIC_CATEGORICAL = ("sex_code", "education_code", "marriage_code")
BEHAVIORAL_NUMERIC = (
    "recent_max_delinquency",
    "delinquent_months_6m",
    "delinquency_deterioration",
    "latest_utilization_ratio",
    "payment_coverage_ratio",
    "zero_payment_streak",
    "recent_bill_growth",
)
REQUIRED_COLUMNS = frozenset(
    {
        "customer_id",
        OUTCOME_FIELD,
        "observation_date",
        "credit_limit_ntd",
        *STATIC_CATEGORICAL,
        "age_years",
        *BEHAVIORAL_NUMERIC,
        "risk_band",
        "source_id",
        "source_file_sha256",
        "definition_version",
    }
)


@dataclass(frozen=True)
class SplitSpec:
    """Immutable deterministic split definition."""

    train_fraction: float = 0.60
    calibration_fraction: float = 0.20
    test_fraction: float = 0.20
    version: str = SPLIT_VERSION

    def validate(self) -> None:
        fractions = (self.train_fraction, self.calibration_fraction, self.test_fraction)
        if any(value <= 0 or value >= 1 for value in fractions):
            raise ValueError("all split fractions must be strictly between zero and one")
        if not math.isclose(sum(fractions), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("split fractions must sum exactly to one")


def split_digest(customer_id: int, spec: SplitSpec = SplitSpec()) -> str:
    """Return the stable full SHA-256 split digest for one borrower."""

    spec.validate()
    if isinstance(customer_id, bool) or int(customer_id) <= 0:
        raise ValueError("customer_id must be a positive integer")
    return hashlib.sha256(f"{spec.version}:{int(customer_id)}".encode()).hexdigest()


def stable_split_assignments(
    customer_ids: Iterable[int], spec: SplitSpec = SplitSpec()
) -> dict[int, str]:
    """Assign exact split sizes by stable digest rank across the population."""

    spec.validate()
    identifiers = [int(value) for value in customer_ids]
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError("customer_ids must be non-empty and unique")
    ranked = sorted(identifiers, key=lambda value: (split_digest(value, spec), value))
    train_end = int(len(ranked) * spec.train_fraction)
    calibration_end = train_end + int(len(ranked) * spec.calibration_fraction)
    if train_end <= 0 or calibration_end <= train_end or calibration_end >= len(ranked):
        raise ValueError("population is too small for non-empty exact-rank splits")
    result: dict[int, str] = {}
    for rank, customer_id in enumerate(ranked):
        if rank < train_end:
            result[customer_id] = "train"
        elif rank < calibration_end:
            result[customer_id] = "calibration"
        else:
            result[customer_id] = "test"
    return result


def expected_calibration_error(
    actual: Sequence[int], predicted: Sequence[float], bins: int = 10
) -> float:
    """Calculate equal-width expected calibration error."""

    y_true = np.asarray(actual, dtype=int)
    y_prob = np.asarray(predicted, dtype=float)
    if y_true.size == 0 or y_true.size != y_prob.size:
        raise ValueError("actual and predicted must be equal-length non-empty arrays")
    if np.any(~np.isfinite(y_prob)) or np.any((y_prob < 0) | (y_prob > 1)):
        raise ValueError("predicted probabilities must be finite and within [0, 1]")
    edges = np.linspace(0.0, 1.0, bins + 1)
    bucket = np.minimum(np.digitize(y_prob, edges[1:-1], right=False), bins - 1)
    result = 0.0
    for index in range(bins):
        mask = bucket == index
        if mask.any():
            result += float(mask.mean()) * abs(
                float(y_true[mask].mean()) - float(y_prob[mask].mean())
            )
    return result


def _performance(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    if len(np.unique(actual)) != 2:
        raise ValueError("performance population must contain both outcome classes")
    clipped = np.clip(predicted.astype(float), 1e-12, 1 - 1e-12)
    return {
        "roc_auc": float(roc_auc_score(actual, clipped)),
        "pr_auc": float(average_precision_score(actual, clipped)),
        "brier_score": float(brier_score_loss(actual, clipped)),
        "log_loss": float(log_loss(actual, clipped, labels=[0, 1])),
        "expected_calibration_error_10_bin": expected_calibration_error(actual, clipped),
        "sample_count": int(len(actual)),
        "default_count": int(actual.sum()),
        "default_rate": float(actual.mean()),
        "average_pd": float(clipped.mean()),
    }


def _calibration_diagnostic(
    actual: np.ndarray, predicted: np.ndarray
) -> dict[str, float | str]:
    """Estimate descriptive calibration-in-the-large and slope on a holdout."""

    diagnostic = LogisticRegression(
        C=1e6,
        solver="lbfgs",
        max_iter=2_000,
        random_state=20260727,
    )
    diagnostic.fit(_logit(predicted), actual.astype(int))
    return {
        "method": "descriptive_logistic_actual_on_logit_predicted",
        "calibration_intercept": float(diagnostic.intercept_[0]),
        "calibration_slope": float(diagnostic.coef_[0][0]),
        "use": "diagnostic_only_not_refit",
    }


def _age_band(age: int) -> str:
    if age < 30:
        return "<30"
    if age < 40:
        return "30-39"
    if age < 50:
        return "40-49"
    if age < 60:
        return "50-59"
    return "60+"


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"model input is missing required columns: {missing}")
    data = frame.loc[:, sorted(REQUIRED_COLUMNS)].copy()
    if data.empty:
        raise ValueError("model input is empty")
    if data["customer_id"].isna().any() or data["customer_id"].duplicated().any():
        raise ValueError("customer_id must be non-null and unique")
    targets = set(data[OUTCOME_FIELD].dropna().astype(int).unique())
    if targets != {0, 1} or data[OUTCOME_FIELD].isna().any():
        raise ValueError("next_month_default must contain only 0 and 1 with both classes")
    for field in ("observation_date", "source_id", "source_file_sha256", "definition_version"):
        if data[field].isna().any() or data[field].nunique(dropna=False) != 1:
            raise ValueError(f"{field} must be non-null and constant within a model run")
    hashes = data["source_file_sha256"].astype(str)
    if not hashes.str.fullmatch(r"[0-9a-f]{64}").all():
        raise ValueError("source_file_sha256 must be one lowercase SHA-256 value")
    if (data["credit_limit_ntd"] <= 0).any():
        raise ValueError("credit_limit_ntd must be positive before log transformation")
    data["log_credit_limit"] = np.log1p(data["credit_limit_ntd"].astype(float))
    data["age_band"] = data["age_years"].astype(int).map(_age_band)
    assignments = stable_split_assignments(data["customer_id"].astype(int).tolist())
    data["split"] = data["customer_id"].astype(int).map(assignments)
    if set(data["split"]) != {"train", "calibration", "test"}:
        raise ValueError("all three split populations must be non-empty")
    return data.sort_values("customer_id").reset_index(drop=True)


def _feature_contract(model_name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if model_name == "static":
        return STATIC_NUMERIC, STATIC_CATEGORICAL
    if model_name == "behavioral":
        return BEHAVIORAL_NUMERIC, ()
    if model_name == "combined":
        return STATIC_NUMERIC + BEHAVIORAL_NUMERIC, STATIC_CATEGORICAL
    raise ValueError(f"unknown model name: {model_name}")


def _build_pipeline(
    numeric_features: Sequence[str], categorical_features: Sequence[str]
) -> Pipeline:
    transformers: list[tuple[str, Any, Sequence[str]]] = []
    if numeric_features:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scaler", StandardScaler()),
                    ]
                ),
                list(numeric_features),
            )
        )
    if categorical_features:
        transformers.append(
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", drop=None),
                list(categorical_features),
            )
        )
    return Pipeline(
        [
            (
                "preprocessor",
                ColumnTransformer(transformers=transformers, remainder="drop"),
            ),
            (
                "logistic",
                LogisticRegression(
                    C=1.0,
                    solver="lbfgs",
                    max_iter=2_000,
                    random_state=20260727,
                ),
            ),
        ]
    )


def _logit(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(probability.astype(float), 1e-12, 1 - 1e-12)
    return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)


def _segment_rows(
    test: pd.DataFrame, actual: np.ndarray, predicted: np.ndarray
) -> list[dict[str, Any]]:
    working = test.loc[
        :,
        [
            "customer_id",
            "sex_code",
            "education_code",
            "marriage_code",
            "age_band",
            "risk_band",
        ],
    ].copy()
    working["actual_default"] = actual.astype(int)
    working["predicted_pd"] = predicted.astype(float)
    rows: list[dict[str, Any]] = []
    for field in (
        "sex_code",
        "education_code",
        "marriage_code",
        "age_band",
        "risk_band",
    ):
        for value, group in working.groupby(field, dropna=False, sort=True):
            y_true = group["actual_default"].to_numpy(dtype=int)
            y_prob = group["predicted_pd"].to_numpy(dtype=float)
            rows.append(
                {
                    "segment_field": field,
                    "segment_value": str(value),
                    "sample_count": int(len(group)),
                    "default_count": int(y_true.sum()),
                    "default_rate": float(y_true.mean()),
                    "average_pd": float(y_prob.mean()),
                    "brier_score": float(brier_score_loss(y_true, y_prob)),
                }
            )
    return rows


def _coefficients(pipeline: Pipeline) -> list[dict[str, Any]]:
    preprocessor = pipeline.named_steps["preprocessor"]
    logistic = pipeline.named_steps["logistic"]
    names = preprocessor.get_feature_names_out()
    coefficients = logistic.coef_[0]
    return sorted(
        (
            {"transformed_feature": str(name), "coefficient": float(value)}
            for name, value in zip(names, coefficients, strict=True)
        ),
        key=lambda row: (-abs(row["coefficient"]), row["transformed_feature"]),
    )


def _assert_no_leakage(features: Iterable[str]) -> None:
    feature_set = frozenset(features)
    forbidden = sorted(feature_set.intersection(IDENTIFIER_AND_METADATA_FIELDS))
    if forbidden:
        raise ValueError(f"forbidden leakage or metadata features requested: {forbidden}")


def _fit_one(
    data: pd.DataFrame,
    model_name: str,
    *,
    model_run_id: str,
    model_definition_version: str,
) -> dict[str, Any]:
    numeric, categorical = _feature_contract(model_name)
    features = numeric + categorical
    _assert_no_leakage(features)
    train = data.loc[data["split"] == "train"].copy()
    calibration = data.loc[data["split"] == "calibration"].copy()
    test = data.loc[data["split"] == "test"].copy()
    for name, population in (
        ("train", train),
        ("calibration", calibration),
        ("test", test),
    ):
        if population[OUTCOME_FIELD].nunique() != 2:
            raise ValueError(f"{name} population must contain both outcome classes")

    pipeline = _build_pipeline(numeric, categorical)
    pipeline.fit(train.loc[:, features], train[OUTCOME_FIELD].astype(int))
    calibration_raw = pipeline.predict_proba(calibration.loc[:, features])[:, 1]
    calibrator = LogisticRegression(
        C=1e6,
        solver="lbfgs",
        max_iter=2_000,
        random_state=20260727,
    )
    calibrator.fit(_logit(calibration_raw), calibration[OUTCOME_FIELD].astype(int))
    test_raw = pipeline.predict_proba(test.loc[:, features])[:, 1]
    calibration_pd = calibrator.predict_proba(_logit(calibration_raw))[:, 1]
    test_pd = calibrator.predict_proba(_logit(test_raw))[:, 1]
    if np.any(~np.isfinite(test_pd)) or np.any((test_pd < 0) | (test_pd > 1)):
        raise ValueError("calibrated test predictions must be finite probabilities")

    test_predictions = []
    for position, (_, row) in enumerate(test.iterrows()):
        test_predictions.append(
            {
                "borrower_id": int(row["customer_id"]),
                "actual_default": int(row[OUTCOME_FIELD]),
                "predicted_pd": float(test_pd[position]),
                "raw_pd": float(test_raw[position]),
                "split": "test",
            }
        )

    return {
        "model_run_id": model_run_id,
        "model_definition_version": model_definition_version,
        "model_type": "logistic_regression_with_disjoint_platt_calibration",
        "feature_names": list(features),
        "fit_counts": {
            "train": int(len(train)),
            "calibration": int(len(calibration)),
            "test": int(len(test)),
        },
        "preprocessing": {
            "fit_population": "train_only",
            "numeric": "train_median_imputation_with_indicator_then_standardization",
            "categorical": "one_hot_handle_unknown_ignore",
        },
        "calibration": {
            "method": "platt_on_disjoint_calibration",
            "fit_population": "calibration_only",
            "platt_fit_slope": float(calibrator.coef_[0][0]),
            "platt_fit_intercept": float(calibrator.intercept_[0]),
        },
        "metrics": {
            "calibration": _performance(
                calibration[OUTCOME_FIELD].to_numpy(dtype=int), calibration_pd
            ),
            "test": {
                **_performance(test[OUTCOME_FIELD].to_numpy(dtype=int), test_pd),
                **_calibration_diagnostic(
                    test[OUTCOME_FIELD].to_numpy(dtype=int), test_pd
                ),
            },
        },
        "coefficients": _coefficients(pipeline),
        "segment_stability": _segment_rows(
            test, test[OUTCOME_FIELD].to_numpy(dtype=int), test_pd
        ),
        "test_predictions": test_predictions,
    }


def build_model_packet(
    frame: pd.DataFrame,
    *,
    source_run_id: str,
    model_run_id: str,
    generated_at: str,
    model_definition_version: str = MODEL_DEFINITION_VERSION,
) -> dict[str, Any]:
    """Build a deterministic, JSON-serializable three-model evidence packet."""

    if not source_run_id.strip() or not model_run_id.strip():
        raise ValueError("source_run_id and model_run_id are required")
    if not model_definition_version.strip() or not generated_at.strip():
        raise ValueError("model_definition_version and generated_at are required")
    data = _prepare_frame(frame)
    models = {
        name: _fit_one(
            data,
            name,
            model_run_id=model_run_id,
            model_definition_version=model_definition_version,
        )
        for name in MODEL_NAMES
    }
    test_ids = [
        int(value) for value in data.loc[data["split"] == "test", "customer_id"].tolist()
    ]
    for name, result in models.items():
        prediction_ids = [row["borrower_id"] for row in result["test_predictions"]]
        if prediction_ids != test_ids:
            raise ValueError(f"{name} test predictions do not reconcile to split membership")

    population = [
        {
            "borrower_id": int(row.customer_id),
            "actual_default": int(row.next_month_default),
            "split": str(row.split),
            "sex_code": int(row.sex_code),
            "education_code": int(row.education_code),
            "marriage_code": int(row.marriage_code),
            "age_band": str(row.age_band),
            "risk_band": str(row.risk_band),
        }
        for row in data.itertuples(index=False)
    ]
    split_counts = data.groupby("split").size().to_dict()
    source_metadata = {
        "source_id": str(data["source_id"].iloc[0]),
        "source_file_sha256": str(data["source_file_sha256"].iloc[0]),
        "source_definition_version": str(data["definition_version"].iloc[0]),
        "observation_date": str(data["observation_date"].iloc[0]),
        "borrower_count": int(len(data)),
        "observed_default_count": int(data[OUTCOME_FIELD].sum()),
    }
    static_test = models["static"]["metrics"]["test"]
    return {
        "schema_version": "1.0",
        "run_id": model_run_id,
        "model_run_id": model_run_id,
        "source_run_id": source_run_id,
        "definition_version": model_definition_version,
        "model_definition_version": model_definition_version,
        "generated_at": generated_at,
        "status": "retrospective_internal_benchmark_only",
        "source_sha256": source_metadata["source_file_sha256"],
        "source_metadata": source_metadata,
        "validation_design": {
            "strategy": "stable_customer_id_sha256_rank_60_20_20",
            "split_version": SPLIT_VERSION,
            "split_algorithm": "sha256_rank",
            "split_key": "customer_id",
            "split_input_contract": (
                "UTF-8 bytes of split_version + ':' + base-10 integer borrower_id"
            ),
            "split_order": "ascending_full_hex_digest_then_borrower_id",
            "train_fraction": 0.60,
            "calibration_fraction": 0.20,
            "test_fraction": 0.20,
            "split_thresholds": {
                "train_rank_end_exclusive": int(len(data) * 0.60),
                "calibration_rank_end_exclusive": int(len(data) * 0.80),
                "population_size": int(len(data)),
            },
            "split_counts": {
                "train": int(split_counts["train"]),
                "calibration": int(split_counts["calibration"]),
                "test": int(split_counts["test"]),
            },
            "population_membership_artifact": "top_level_population",
            "row_predictions_scope": "test_only",
            "genuine_time_direction": False,
            "train_end": None,
            "test_start": None,
            "temporal_gate_eligible": False,
            "reason": (
                "The source has one common borrower observation date and no "
                "borrower-level origination/performance timestamp for temporal splitting."
            ),
        },
        "feature_controls": {
            "allowlists": {
                name: list(sum(_feature_contract(name), ())) for name in MODEL_NAMES
            },
            "excluded_features": sorted(IDENTIFIER_AND_METADATA_FIELDS),
            "preprocessing_fit_split": "train",
            "model_fit_split": "train",
            "calibration_fit_split": "calibration",
            "final_evaluation_split": "test",
        },
        "leakage_controls": {
            "outcome_field": OUTCOME_FIELD,
            "forbidden_features": sorted(IDENTIFIER_AND_METADATA_FIELDS),
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
        "comparison": {
            name: {
                "test_roc_auc_delta_vs_static": float(
                    result["metrics"]["test"]["roc_auc"] - static_test["roc_auc"]
                ),
                "test_pr_auc_delta_vs_static": float(
                    result["metrics"]["test"]["pr_auc"] - static_test["pr_auc"]
                ),
                "test_brier_delta_vs_static": float(
                    result["metrics"]["test"]["brier_score"] - static_test["brier_score"]
                ),
            }
            for name, result in models.items()
        },
        "component_scope": {
            "pd": {
                "status": "prototype_retrospective_internal_benchmark",
            },
            "stage": {
                "status": "not_estimated",
                "reason": "human approval and approved SICR/default rules required",
            },
            "ead": {
                "status": "not_estimated",
                "reason": "no eligible exposure-at-default or drawdown data",
            },
            "lgd": {
                "status": "not_estimated",
                "reason": "no recovery, cost, collateral, or cash-flow timing data",
            },
            "ecl": {
                "status": "not_estimated",
                "reason": "requires approved PD, Stage, EAD, LGD, scenarios, and discounting",
            },
            "scenario_sensitivity": {
                "status": "not_estimated",
                "reason": "no approved macroeconomic or behavioral shock values",
            },
        },
        "limitations": [
            "No genuine time-direction validation is possible from one common observation date.",
            "The split is deterministic and out-of-sample but cross-sectional, not temporal.",
            "Observed target is dataset-provided next-month default, not a bank-approved default definition.",
            "Undocumented source category and repayment-status codes remain preserved.",
            "Recent bill growth has an inverse observed direction and zero-payment streak is non-monotonic in Wave 1; neither is redefined here.",
            "Metrics are retrospective internal benchmark evidence and are not Gate 4 eligible.",
        ],
    }
