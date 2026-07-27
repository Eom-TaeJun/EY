"""Deterministic and leakage-control tests for the Wave 2 PD builder."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.models import run_pd_prototype
from src.models.pd_prototype import (
    BEHAVIORAL_NUMERIC,
    MODEL_NAMES,
    SPLIT_VERSION,
    build_model_packet,
    split_digest,
    stable_split_assignments,
)


def _synthetic_frame(rows: int = 1_000) -> pd.DataFrame:
    """Create deterministic test-only inputs; no synthetic result is published."""

    rng = np.random.default_rng(20260727)
    customer_id = np.arange(1, rows + 1)
    recent_delinquency = rng.integers(0, 4, size=rows)
    delinquent_months = rng.integers(0, 7, size=rows)
    age = rng.integers(21, 75, size=rows)
    linear = -2.2 + 0.7 * recent_delinquency + 0.25 * delinquent_months
    probability = 1 / (1 + np.exp(-linear))
    target = (rng.random(rows) < probability).astype(int)
    frame = pd.DataFrame(
        {
            "customer_id": customer_id,
            "next_month_default": target,
            "observation_date": pd.Timestamp("2005-09-30").date(),
            "credit_limit_ntd": rng.integers(10_000, 1_000_001, size=rows),
            "sex_code": rng.integers(1, 3, size=rows),
            "education_code": rng.integers(0, 7, size=rows),
            "marriage_code": rng.integers(0, 4, size=rows),
            "age_years": age,
            "recent_max_delinquency": recent_delinquency,
            "delinquent_months_6m": delinquent_months,
            "delinquency_deterioration": rng.integers(-3, 4, size=rows),
            "latest_utilization_ratio": rng.normal(0.7, 0.5, size=rows),
            "payment_coverage_ratio": rng.lognormal(-2.0, 1.0, size=rows),
            "zero_payment_streak": rng.integers(0, 7, size=rows),
            "recent_bill_growth": rng.normal(0.0, 0.8, size=rows),
            "risk_band": np.where(recent_delinquency >= 2, "High", "Low"),
            "source_id": "synthetic_unit_test_only",
            "source_file_sha256": "a" * 64,
            "definition_version": "test",
        }
    )
    frame.loc[frame.index[::11], "payment_coverage_ratio"] = np.nan
    frame.loc[frame.index[::17], "recent_bill_growth"] = np.nan
    return frame


@pytest.fixture(scope="module")
def packet() -> dict[str, object]:
    return build_model_packet(
        _synthetic_frame(),
        source_run_id="W1-TEST-001",
        model_run_id="W2-PD-TEST-001",
        generated_at="2026-07-27T00:00:00+09:00",
    )


def test_sha256_rank_split_is_exact_stable_and_recomputable() -> None:
    identifiers = list(range(1, 1001))
    first = stable_split_assignments(identifiers)
    second = stable_split_assignments(reversed(identifiers))

    assert first == second
    assert list(first.values()).count("train") == 600
    assert list(first.values()).count("calibration") == 200
    assert list(first.values()).count("test") == 200
    expected_first = min(identifiers, key=lambda value: (split_digest(value), value))
    assert first[expected_first] == "train"
    assert SPLIT_VERSION == "customer_sha256_v1"


def test_packet_has_exhaustive_population_and_fixed_feature_controls(
    packet: dict[str, object],
) -> None:
    population = packet["population"]
    assert isinstance(population, list)
    assert len(population) == 1_000
    assert len({row["borrower_id"] for row in population}) == 1_000
    assert {row["split"] for row in population} == {"train", "calibration", "test"}
    assert all("risk_band" in row for row in population)
    assert all("marriage_code" in row for row in population)

    controls = packet["feature_controls"]
    assert controls["preprocessing_fit_split"] == "train"
    assert controls["calibration_fit_split"] == "calibration"
    excluded = set(controls["excluded_features"])
    assert {"next_month_default", "customer_id", "risk_points", "risk_band"} <= excluded
    for allowlist in controls["allowlists"].values():
        assert not excluded.intersection(allowlist)


def test_each_model_metrics_recompute_from_test_rows(packet: dict[str, object]) -> None:
    models = packet["models"]
    assert set(models) == set(MODEL_NAMES)
    expected_test_ids = {
        row["borrower_id"] for row in packet["population"] if row["split"] == "test"
    }
    for model in models.values():
        predictions = model["test_predictions"]
        assert len(predictions) == 200
        assert {row["borrower_id"] for row in predictions} == expected_test_ids
        actual = np.array([row["actual_default"] for row in predictions])
        predicted = np.array([row["predicted_pd"] for row in predictions])
        reported = model["metrics"]["test"]
        assert reported["roc_auc"] == pytest.approx(roc_auc_score(actual, predicted))
        assert reported["brier_score"] == pytest.approx(
            brier_score_loss(actual, predicted)
        )
        assert reported["use"] == "diagnostic_only_not_refit"
        assert "calibration_intercept" in reported
        assert "calibration_slope" in reported
        assert "platt_fit_slope" in model["calibration"]
        assert "slope" not in model["calibration"]
        assert all(0 <= value <= 1 for value in predicted)


def test_segment_diagnostics_reconcile_to_test_population(
    packet: dict[str, object],
) -> None:
    for model in packet["models"].values():
        rows = model["segment_stability"]
        for field in (
            "sex_code",
            "education_code",
            "marriage_code",
            "age_band",
            "risk_band",
        ):
            assert sum(
                row["sample_count"] for row in rows if row["segment_field"] == field
            ) == 200


def test_behavioral_contradictions_are_retained_not_redefined(
    packet: dict[str, object],
) -> None:
    behavioral_features = packet["models"]["behavioral"]["feature_names"]
    assert set(behavioral_features) == set(BEHAVIORAL_NUMERIC)
    assert "recent_bill_growth" in behavioral_features
    assert "zero_payment_streak" in behavioral_features
    limitations = " ".join(packet["limitations"])
    assert "inverse observed direction" in limitations
    assert "non-monotonic" in limitations


def test_builder_rejects_duplicate_borrower() -> None:
    frame = _synthetic_frame(100)
    frame.loc[1, "customer_id"] = frame.loc[0, "customer_id"]
    with pytest.raises(ValueError, match="unique"):
        build_model_packet(
            frame,
            source_run_id="W1-TEST-001",
            model_run_id="W2-PD-TEST-001",
            generated_at="2026-07-27T00:00:00+09:00",
        )


def test_cli_refuses_to_overwrite_before_querying_database(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing.json"
    output.write_text(json.dumps({"validated": True}), encoding="utf-8")

    def _must_not_query(*args: object, **kwargs: object) -> pd.DataFrame:
        raise AssertionError("database must not be queried for an existing output")

    monkeypatch.setattr(run_pd_prototype, "_load_frame", _must_not_query)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_pd_prototype.main(
            [
                "--database-url",
                "unused",
                "--source-run-id",
                "W1-TEST-001",
                "--model-run-id",
                "W2-PD-TEST-001",
                "--generated-at",
                "2026-07-27T00:00:00+09:00",
                "--output",
                str(output),
            ]
        )
