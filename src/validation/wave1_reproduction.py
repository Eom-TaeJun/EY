"""Independently derive Wave 1 gate evidence from a validation snapshot.

The input is not a gate packet.  It is a deterministic export of source,
reconciliation, SQL-test, signal-definition, signal-outcome, and risk-band
facts.  This module recomputes differences, coverage, rates, and gate statuses
without invoking or repairing Builder SQL.

Missing input produces ``blocked`` output and a non-zero exit.  Existing output
files are never overwritten by the CLI.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from .gate_evidence import (
    GateContractReport,
    GateEvidenceValidator,
    GateThresholds,
    ValidationIssue,
    load_json_object,
    load_thresholds,
)


@dataclass(frozen=True)
class Wave1ReproductionReport:
    """Serializable independent reproduction result."""

    schema_version: str
    run_id: str | None
    generated_at: str
    status: str
    issues: tuple[ValidationIssue, ...]
    gate_packets: tuple[dict[str, Any], ...]
    contract_reports: tuple[GateContractReport, ...]
    verified_findings: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "issues": [asdict(issue) for issue in self.issues],
            "gate_packets": list(self.gate_packets),
            "contract_reports": [report.to_dict() for report in self.contract_reports],
            "verified_findings": dict(self.verified_findings),
        }


def reproduce_wave1(
    snapshot: object,
    *,
    thresholds: GateThresholds | None = None,
    generated_at: str | None = None,
    artifact_root: Path | None = None,
) -> Wave1ReproductionReport:
    """Recompute Gate 1-3 evidence from a snapshot and validate every packet."""

    current_thresholds = thresholds or GateThresholds()
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    snapshot_issues = _validate_snapshot_root(snapshot)
    if not isinstance(snapshot, Mapping):
        return _blocked_report(timestamp, snapshot_issues)

    run_id = snapshot.get("run_id") if isinstance(snapshot.get("run_id"), str) else None
    source = _mapping(snapshot.get("source"))
    core = _mapping(snapshot.get("core"))
    list_issues: list[ValidationIssue] = []
    sql_tests = _required_mapping_list(
        snapshot.get("sql_tests"), "$.sql_tests", list_issues
    )
    signals = _mapping(snapshot.get("signals"))

    source_metrics, source_issues = _reproduce_source(source)
    core_metrics, core_issues = _reproduce_core(core, sql_tests, current_thresholds)
    core_metrics["raw_rows"] = source_metrics.get("raw_rows")
    signal_metrics, signal_issues = _reproduce_signals(
        signals,
        borrower_rows=core_metrics.get("borrower_rows"),
        minimum_signals=current_thresholds.minimum_signal_count,
    )
    issues = [
        *snapshot_issues,
        *list_issues,
        *source_issues,
        *core_issues,
        *signal_issues,
    ]

    producer = {
        "role": "Validation",
        "command": (
            "python -m src.validation.wave1_reproduction "
            "--snapshot <snapshot.json> --output <validation.json>"
        ),
    }
    gate_1_issues = [*snapshot_issues, *source_issues]
    gate_2_issues = [*gate_1_issues, *list_issues, *core_issues]
    gate_3_issues = [*gate_2_issues, *signal_issues]
    gate_1 = _gate_1_packet(run_id, timestamp, producer, source_metrics, gate_1_issues)
    gate_2 = _gate_2_packet(run_id, timestamp, producer, core_metrics, gate_2_issues)
    gate_3 = _gate_3_packet(run_id, timestamp, producer, signal_metrics, gate_3_issues)
    packets = (gate_1, gate_2, gate_3)

    validator = GateEvidenceValidator(
        current_thresholds,
        artifact_root=artifact_root,
    )
    contract_reports = tuple(
        validator.validate(packet, expected_gate=gate, expected_run_id=run_id)
        for gate, packet in enumerate(packets, start=1)
    )
    all_valid = not issues and all(report.valid for report in contract_reports)

    verified_findings: dict[str, Any] = {}
    if all_valid:
        verified_findings = {
            "source_rows": source_metrics["source_rows"],
            "raw_rows": source_metrics["raw_rows"],
            "borrower_rows": core_metrics["borrower_rows"],
            "account_month_rows": core_metrics["account_month_rows"],
            "sql_test_count": core_metrics["sql_test_count"],
            "sql_failed_count": core_metrics["sql_failed_count"],
            "signal_outcomes": signal_metrics["signal_outcomes"],
            "risk_band_outcomes": signal_metrics["risk_band_outcomes"],
        }

    return Wave1ReproductionReport(
        schema_version="1.0",
        run_id=run_id,
        generated_at=timestamp,
        status="pass" if all_valid else "blocked" if snapshot_issues else "fail",
        issues=tuple(issues),
        gate_packets=packets,
        contract_reports=contract_reports,
        verified_findings=verified_findings,
    )


def _validate_snapshot_root(snapshot: object) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(snapshot, Mapping):
        return [
            ValidationIssue(
                "snapshot_not_object", "$", "Wave 1 snapshot must be a JSON object"
            )
        ]
    if snapshot.get("schema_version") != "1.0":
        issues.append(
            ValidationIssue(
                "unsupported_snapshot_version",
                "$.schema_version",
                "snapshot schema_version must equal '1.0'",
            )
        )
    run_id = snapshot.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        issues.append(
            ValidationIssue("missing_run_id", "$.run_id", "snapshot run_id is required")
        )
    for field in ("source", "core", "signals"):
        if not isinstance(snapshot.get(field), Mapping):
            issues.append(
                ValidationIssue(
                    "missing_snapshot_section",
                    f"$.{field}",
                    f"snapshot section {field!r} must be an object",
                )
            )
    if not isinstance(snapshot.get("sql_tests"), list):
        issues.append(
            ValidationIssue(
                "missing_sql_tests",
                "$.sql_tests",
                "sql_tests must be a list, even when no tests ran",
            )
        )
    return issues


def _reproduce_source(
    source: Mapping[str, Any],
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    source_id = _required_text(source, "source_id", "$.source", issues)
    registry_path = _required_text(source, "registry_path", "$.source", issues)
    sha256 = _required_text(source, "sha256", "$.source", issues)
    source_rows = _required_int(source, "source_rows", "$.source", issues, positive=True)
    source_columns = _required_int(
        source, "source_columns", "$.source", issues, positive=True
    )
    raw_rows = _required_int(source, "raw_rows", "$.source", issues, positive=True)
    unlogged_rejects = _required_int(
        source, "unlogged_rejects", "$.source", issues, nonnegative=True
    )
    registered = source.get("registered")
    if registered is not True:
        issues.append(
            ValidationIssue(
                "source_not_registered",
                "$.source.registered",
                "registered must be true",
            )
        )
    difference = (
        raw_rows - source_rows
        if source_rows is not None and raw_rows is not None
        else None
    )
    if difference not in (None, 0):
        issues.append(
            ValidationIssue(
                "raw_row_mismatch",
                "$.source.raw_rows",
                f"raw_rows - source_rows equals {difference}, expected zero",
            )
        )
    if unlogged_rejects not in (None, 0):
        issues.append(
            ValidationIssue(
                "unlogged_rejects",
                "$.source.unlogged_rejects",
                "unlogged_rejects must equal zero",
            )
        )
    return (
        {
            "source_id": source_id,
            "registry_path": registry_path,
            "sha256": sha256,
            "source_rows": source_rows,
            "source_columns": source_columns,
            "raw_rows": raw_rows,
            "difference": difference,
            "unlogged_rejects": unlogged_rejects,
            "registered": registered,
        },
        issues,
    )


def _reproduce_core(
    core: Mapping[str, Any],
    sql_tests: Sequence[Mapping[str, Any]],
    thresholds: GateThresholds,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    borrower_rows = _required_int(
        core, "borrower_rows", "$.core", issues, positive=True
    )
    account_month_rows = _required_int(
        core, "account_month_rows", "$.core", issues, positive=True
    )
    months = _required_int(
        core, "months_per_borrower", "$.core", issues, positive=True
    )
    duplicate_count = _required_int(
        core, "duplicate_borrower_keys", "$.core", issues, nonnegative=True
    )
    account_month_duplicate_count = _required_int(
        core, "duplicate_account_month_keys", "$.core", issues, nonnegative=True
    )
    null_key_count = _required_int(
        core, "null_borrower_keys", "$.core", issues, nonnegative=True
    )
    orphan_count = _required_int(
        core, "orphan_account_month_rows", "$.core", issues, nonnegative=True
    )
    invalid_code_rows = _required_int(
        core, "invalid_code_rows", "$.core", issues, nonnegative=True
    )
    missing_required_history_rows = _required_int(
        core, "missing_required_history_rows", "$.core", issues, nonnegative=True
    )
    expected_account_month_rows = (
        borrower_rows * months
        if borrower_rows is not None and months is not None
        else None
    )
    row_difference = (
        account_month_rows - expected_account_month_rows
        if account_month_rows is not None and expected_account_month_rows is not None
        else None
    )
    if months not in (None, 6):
        issues.append(
            ValidationIssue(
                "invalid_month_count",
                "$.core.months_per_borrower",
                "the approved source requires six history months",
            )
        )
    for field, value in (
        ("duplicate_borrower_keys", duplicate_count),
        ("duplicate_account_month_keys", account_month_duplicate_count),
        ("null_borrower_keys", null_key_count),
        ("orphan_account_month_rows", orphan_count),
        ("invalid_code_rows", invalid_code_rows),
        ("missing_required_history_rows", missing_required_history_rows),
    ):
        if value not in (None, 0):
            issues.append(
                ValidationIssue(
                    "core_integrity_failure",
                    f"$.core.{field}",
                    f"{field} must equal zero",
                )
            )
    if row_difference not in (None, thresholds.row_count_difference):
        issues.append(
            ValidationIssue(
                "account_month_row_mismatch",
                "$.core.account_month_rows",
                "account-month rows do not match borrower_rows × months_per_borrower",
            )
        )

    bill = _amount_reconciliation(core, "bill", thresholds, issues)
    payment = _amount_reconciliation(core, "payment", thresholds, issues)
    test_metrics, test_issues = _reproduce_sql_tests(sql_tests, thresholds)
    issues.extend(test_issues)
    return (
        {
            "borrower_rows": borrower_rows,
            "account_month_rows": account_month_rows,
            "months_per_borrower": months,
            "expected_account_month_rows": expected_account_month_rows,
            "row_difference": row_difference,
            "duplicate_count": duplicate_count,
            "account_month_duplicate_count": account_month_duplicate_count,
            "null_key_count": null_key_count,
            "orphan_count": orphan_count,
            "invalid_code_rows": invalid_code_rows,
            "missing_required_history_rows": missing_required_history_rows,
            "bill": bill,
            "payment": payment,
            **test_metrics,
        },
        issues,
    )


def _amount_reconciliation(
    core: Mapping[str, Any],
    prefix: str,
    thresholds: GateThresholds,
    issues: list[ValidationIssue],
) -> dict[str, str | None]:
    source_total = _required_decimal(
        core, f"{prefix}_wide_total", "$.core", issues
    )
    derived_total = _required_decimal(
        core, f"{prefix}_long_total", "$.core", issues
    )
    difference = (
        derived_total - source_total
        if source_total is not None and derived_total is not None
        else None
    )
    if difference is not None and abs(difference) > thresholds.floating_amount_tolerance:
        issues.append(
            ValidationIssue(
                "amount_reconciliation_failure",
                f"$.core.{prefix}_long_total",
                f"{prefix} difference {difference} exceeds configured tolerance "
                f"{thresholds.floating_amount_tolerance}",
            )
        )
    return {
        "source_total": str(source_total) if source_total is not None else None,
        "derived_total": str(derived_total) if derived_total is not None else None,
        "difference": str(difference) if difference is not None else None,
    }


def _reproduce_sql_tests(
    sql_tests: Sequence[Mapping[str, Any]],
    thresholds: GateThresholds,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    failed_count = 0
    for index, test in enumerate(sql_tests):
        path = f"$.sql_tests[{index}]"
        test_id = test.get("test_id")
        if not isinstance(test_id, str) or not test_id.strip():
            issues.append(
                ValidationIssue("invalid_test_id", f"{path}.test_id", "test_id is required")
            )
            continue
        if test_id in seen:
            issues.append(
                ValidationIssue(
                    "duplicate_test_id",
                    f"{path}.test_id",
                    f"duplicate test_id is forbidden: {test_id}",
                )
            )
            continue
        seen.add(test_id)
        status = test.get("status")
        if status != "pass":
            failed_count += 1
            issues.append(
                ValidationIssue(
                    "sql_test_not_pass",
                    f"{path}.status",
                    f"{test_id} status is {status!r}, expected 'pass'",
                )
            )
        failed_rows = test.get("failed_rows")
        if not isinstance(failed_rows, int) or isinstance(failed_rows, bool):
            issues.append(
                ValidationIssue(
                    "invalid_failed_rows",
                    f"{path}.failed_rows",
                    "failed_rows must be an integer",
                )
            )
        elif failed_rows != 0:
            failed_count += status == "pass"
            issues.append(
                ValidationIssue(
                    "failed_rows_nonzero",
                    f"{path}.failed_rows",
                    f"{test_id} has {failed_rows} failed rows",
                )
            )
        for required_field in ("tested_rows", "severity", "affected_object"):
            if required_field not in test or test[required_field] in (None, ""):
                issues.append(
                    ValidationIssue(
                        "incomplete_test_evidence",
                        f"{path}.{required_field}",
                        f"{required_field} is required by the test catalog",
                    )
                )
    if len(seen) < thresholds.minimum_sql_test_count:
        issues.append(
            ValidationIssue(
                "insufficient_sql_tests",
                "$.sql_tests",
                f"{len(seen)} unique SQL tests found; "
                f"{thresholds.minimum_sql_test_count} required",
            )
        )
    return (
        {"sql_test_count": len(seen), "sql_failed_count": failed_count},
        issues,
    )


def _reproduce_signals(
    signals: Mapping[str, Any],
    *,
    borrower_rows: object,
    minimum_signals: int,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    definition_version = _required_text(
        signals, "definition_version", "$.signals", issues
    )
    definitions = _required_mapping_list(
        signals.get("definitions"), "$.signals.definitions", issues
    )
    outcomes = _required_mapping_list(
        signals.get("outcomes"), "$.signals.outcomes", issues
    )
    risk_bands = _required_mapping_list(
        signals.get("risk_bands"), "$.signals.risk_bands", issues
    )
    query_manifest = _required_text(
        signals, "query_manifest", "$.signals", issues
    )

    definition_ids: set[str] = set()
    timing_violations = 0
    leakage_violations = 0
    reproducible_ids: set[str] = set()
    for index, definition in enumerate(definitions):
        path = f"$.signals.definitions[{index}]"
        signal_id = definition.get("signal_id")
        if not isinstance(signal_id, str) or not signal_id.strip():
            issues.append(
                ValidationIssue(
                    "invalid_signal_id", f"{path}.signal_id", "signal_id is required"
                )
            )
            continue
        if signal_id in definition_ids:
            issues.append(
                ValidationIssue(
                    "duplicate_signal_id",
                    f"{path}.signal_id",
                    f"duplicate signal definition: {signal_id}",
                )
            )
            continue
        definition_ids.add(signal_id)
        for field in ("economic_rationale", "observation_timing", "sql_artifact"):
            if not isinstance(definition.get(field), str) or not definition[field].strip():
                issues.append(
                    ValidationIssue(
                        "incomplete_signal_definition",
                        f"{path}.{field}",
                        f"{field} is required",
                    )
                )
        timing_status = definition.get("timing_status")
        leakage_status = definition.get("leakage_status")
        if timing_status != "pass":
            timing_violations += 1
            issues.append(
                ValidationIssue(
                    "observation_timing_failure",
                    f"{path}.timing_status",
                    f"{signal_id} timing_status must equal 'pass'",
                )
            )
        if leakage_status != "pass":
            leakage_violations += 1
            issues.append(
                ValidationIssue(
                    "leakage_failure",
                    f"{path}.leakage_status",
                    f"{signal_id} leakage_status must equal 'pass'",
                )
            )
        if (
            isinstance(definition.get("sql_artifact"), str)
            and definition["sql_artifact"].strip()
        ):
            reproducible_ids.add(signal_id)

    if len(definition_ids) < minimum_signals:
        issues.append(
            ValidationIssue(
                "insufficient_signals",
                "$.signals.definitions",
                f"{len(definition_ids)} signals found; {minimum_signals} required",
            )
        )

    (
        signal_outcomes,
        outcome_issues,
        covered_ids,
        portfolio_default_count,
    ) = _validate_outcome_rows(
        outcomes,
        valid_ids=definition_ids,
        expected_population=borrower_rows,
        path="$.signals.outcomes",
        group_field="bucket",
    )
    issues.extend(outcome_issues)
    (
        risk_band_outcomes,
        band_issues,
        _,
        risk_band_default_count,
    ) = _validate_outcome_rows(
        risk_bands,
        valid_ids=None,
        expected_population=borrower_rows,
        path="$.signals.risk_bands",
        group_field="risk_band",
    )
    issues.extend(band_issues)
    if (
        portfolio_default_count is not None
        and risk_band_default_count is not None
        and portfolio_default_count != risk_band_default_count
    ):
        issues.append(
            ValidationIssue(
                "default_total_mismatch",
                "$.signals.risk_bands",
                "risk-band total defaults do not match the per-signal portfolio total",
            )
        )
    missing_summaries = definition_ids - covered_ids
    if missing_summaries:
        issues.append(
            ValidationIssue(
                "missing_signal_outcomes",
                "$.signals.outcomes",
                "signals without outcome summaries: " + ", ".join(sorted(missing_summaries)),
            )
        )
    return (
        {
            "definition_version": definition_version,
            "signal_count": len(definition_ids),
            "timing_reviewed_count": len(definition_ids),
            "timing_violation_count": timing_violations,
            "leakage_reviewed_count": len(definition_ids),
            "leakage_violation_count": leakage_violations,
            "summary_row_count": len(signal_outcomes),
            "signals_with_summary": len(covered_ids),
            "invalid_summary_count": len(outcome_issues) + len(band_issues),
            "risk_band_row_count": len(risk_band_outcomes),
            "portfolio_default_count": portfolio_default_count,
            "risk_band_default_count": risk_band_default_count,
            "reproducible_signal_count": len(reproducible_ids),
            "unreproducible_count": len(definition_ids - reproducible_ids),
            "query_manifest": query_manifest,
            "signal_outcomes": signal_outcomes,
            "risk_band_outcomes": risk_band_outcomes,
        },
        issues,
    )


def _validate_outcome_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    valid_ids: set[str] | None,
    expected_population: object,
    path: str,
    group_field: str,
) -> tuple[list[dict[str, Any]], list[ValidationIssue], set[str], int | None]:
    issues: list[ValidationIssue] = []
    normalized: list[dict[str, Any]] = []
    covered_ids: set[str] = set()
    totals: dict[str, tuple[int, int]] = {}
    seen_groups: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        row_path = f"{path}[{index}]"
        signal_id_value = row.get("signal_id")
        signal_id = (
            signal_id_value
            if isinstance(signal_id_value, str) and signal_id_value.strip()
            else "__risk_band__"
        )
        group = row.get(group_field)
        if not isinstance(group, str) or not group.strip():
            issues.append(
                ValidationIssue(
                    "invalid_outcome_group",
                    f"{row_path}.{group_field}",
                    f"{group_field} must be non-blank",
                )
            )
            continue
        if valid_ids is not None and signal_id not in valid_ids:
            issues.append(
                ValidationIssue(
                    "unknown_signal_outcome",
                    f"{row_path}.signal_id",
                    f"outcome references unknown signal {signal_id!r}",
                )
            )
            continue
        key = (signal_id, group)
        if key in seen_groups:
            issues.append(
                ValidationIssue(
                    "duplicate_outcome_group",
                    row_path,
                    f"duplicate outcome group {key}",
                )
            )
            continue
        seen_groups.add(key)
        sample_count = row.get("sample_count")
        default_count = row.get("default_count")
        if (
            not isinstance(sample_count, int)
            or isinstance(sample_count, bool)
            or sample_count <= 0
        ):
            issues.append(
                ValidationIssue(
                    "invalid_sample_count",
                    f"{row_path}.sample_count",
                    "sample_count must be a positive integer",
                )
            )
            continue
        if (
            not isinstance(default_count, int)
            or isinstance(default_count, bool)
            or default_count < 0
            or default_count > sample_count
        ):
            issues.append(
                ValidationIssue(
                    "invalid_default_count",
                    f"{row_path}.default_count",
                    "default_count must be between zero and sample_count",
                )
            )
            continue
        default_rate = Decimal(default_count) / Decimal(sample_count)
        normalized.append(
            {
                "signal_id": None if signal_id == "__risk_band__" else signal_id,
                group_field: group,
                "sample_count": sample_count,
                "default_count": default_count,
                "observed_default_rate": str(default_rate),
            }
        )
        covered_ids.add(signal_id)
        previous_sample, previous_default = totals.get(signal_id, (0, 0))
        totals[signal_id] = (
            previous_sample + sample_count,
            previous_default + default_count,
        )

    if not normalized:
        issues.append(
            ValidationIssue(
                "empty_outcome_summary",
                path,
                "at least one valid outcome row is required",
            )
        )
    if isinstance(expected_population, int) and not isinstance(expected_population, bool):
        for signal_id, (sample_total, _) in totals.items():
            if sample_total != expected_population:
                issues.append(
                    ValidationIssue(
                        "outcome_population_mismatch",
                        path,
                        f"{signal_id} sample total {sample_total} does not equal "
                        f"borrower_rows {expected_population}",
                    )
                )
    default_totals = {default_total for _, default_total in totals.values()}
    if len(default_totals) > 1:
        issues.append(
            ValidationIssue(
                "signal_default_total_mismatch",
                path,
                "all signal summaries must contain the same portfolio default total",
            )
        )
    shared_default_total = next(iter(default_totals)) if len(default_totals) == 1 else None
    return normalized, issues, covered_ids, shared_default_total


def _gate_1_packet(
    run_id: str | None,
    generated_at: str,
    producer: Mapping[str, str],
    metrics: Mapping[str, Any],
    issues: Sequence[ValidationIssue],
) -> dict[str, Any]:
    return _packet(
        gate=1,
        run_id=run_id,
        generated_at=generated_at,
        producer=producer,
        issues=issues,
        checks=[
            _check(
                "source_registered",
                not issues and metrics.get("registered") is True,
                {
                    "registered": metrics.get("registered"),
                    "source_id": metrics.get("source_id"),
                    "registry_path": metrics.get("registry_path"),
                },
            ),
            _check(
                "sha256_recorded",
                not issues,
                {"sha256": metrics.get("sha256")},
            ),
            _check(
                "source_shape_recorded",
                not issues,
                {
                    "source_rows": metrics.get("source_rows"),
                    "source_columns": metrics.get("source_columns"),
                },
            ),
            _check(
                "raw_rows_reconciled",
                not issues,
                {
                    "source_rows": metrics.get("source_rows"),
                    "raw_rows": metrics.get("raw_rows"),
                    "difference": metrics.get("difference"),
                    "unlogged_rejects": metrics.get("unlogged_rejects"),
                },
            ),
        ],
    )


def _gate_2_packet(
    run_id: str | None,
    generated_at: str,
    producer: Mapping[str, str],
    metrics: Mapping[str, Any],
    issues: Sequence[ValidationIssue],
) -> dict[str, Any]:
    passing = not issues
    return _packet(
        gate=2,
        run_id=run_id,
        generated_at=generated_at,
        producer=producer,
        issues=issues,
        checks=[
            _check(
                "primary_key",
                passing,
                {
                    "duplicate_count": metrics.get("duplicate_count"),
                    "null_key_count": metrics.get("null_key_count"),
                    "account_month_duplicate_count": metrics.get(
                        "account_month_duplicate_count"
                    ),
                },
            ),
            _check(
                "foreign_key",
                passing,
                {"orphan_count": metrics.get("orphan_count")},
            ),
            _check(
                "wide_to_long_rows",
                passing,
                {
                    "raw_rows": metrics.get("raw_rows"),
                    "borrower_rows": metrics.get("borrower_rows"),
                    "months_per_borrower": metrics.get("months_per_borrower"),
                    "expected_account_month_rows": metrics.get(
                        "expected_account_month_rows"
                    ),
                    "account_month_rows": metrics.get("account_month_rows"),
                    "difference": metrics.get("row_difference"),
                },
            ),
            _check("bill_amounts", passing, dict(metrics.get("bill") or {})),
            _check("payment_amounts", passing, dict(metrics.get("payment") or {})),
            _check(
                "code_domains",
                passing,
                {
                    "invalid_count": metrics.get("invalid_code_rows"),
                    "missing_required_count": metrics.get(
                        "missing_required_history_rows"
                    ),
                },
            ),
            _check(
                "sql_test_suite",
                passing,
                {
                    "executed_count": metrics.get("sql_test_count"),
                    "failed_count": metrics.get("sql_failed_count"),
                },
            ),
        ],
    )


def _gate_3_packet(
    run_id: str | None,
    generated_at: str,
    producer: Mapping[str, str],
    metrics: Mapping[str, Any],
    issues: Sequence[ValidationIssue],
) -> dict[str, Any]:
    passing = not issues
    return _packet(
        gate=3,
        run_id=run_id,
        generated_at=generated_at,
        producer=producer,
        issues=issues,
        checks=[
            _check("signal_count", passing, {"count": metrics.get("signal_count")}),
            _check(
                "definition_version",
                passing,
                {"version": metrics.get("definition_version")},
            ),
            _check(
                "observation_timing",
                passing,
                {
                    "reviewed_count": metrics.get("timing_reviewed_count"),
                    "violation_count": metrics.get("timing_violation_count"),
                },
            ),
            _check(
                "leakage",
                passing,
                {
                    "reviewed_count": metrics.get("leakage_reviewed_count"),
                    "violation_count": metrics.get("leakage_violation_count"),
                },
            ),
            _check(
                "outcome_summary",
                passing,
                {
                    "summary_row_count": metrics.get("summary_row_count"),
                    "signals_with_summary": metrics.get("signals_with_summary"),
                    "invalid_summary_count": metrics.get("invalid_summary_count"),
                    "risk_band_row_count": metrics.get("risk_band_row_count"),
                    "portfolio_default_count": metrics.get(
                        "portfolio_default_count"
                    ),
                    "risk_band_default_count": metrics.get(
                        "risk_band_default_count"
                    ),
                },
            ),
            _check(
                "sql_reproducibility",
                passing,
                {
                    "reproducible_signal_count": metrics.get(
                        "reproducible_signal_count"
                    ),
                    "unreproducible_count": metrics.get("unreproducible_count"),
                    "query_manifest": metrics.get("query_manifest"),
                },
            ),
        ],
    )


def _packet(
    *,
    gate: int,
    run_id: str | None,
    generated_at: str,
    producer: Mapping[str, str],
    issues: Sequence[ValidationIssue],
    checks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "gate": gate,
        "run_id": run_id,
        "generated_at": generated_at,
        "producer": dict(producer),
        "status": "pass" if not issues else "fail",
        "checks": list(checks),
    }


def _check(check_id: str, passed: bool, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "evidence": dict(evidence),
    }


def _blocked_report(
    generated_at: str, issues: Sequence[ValidationIssue]
) -> Wave1ReproductionReport:
    return Wave1ReproductionReport(
        schema_version="1.0",
        run_id=None,
        generated_at=generated_at,
        status="blocked",
        issues=tuple(issues),
        gate_packets=(),
        contract_reports=(),
        verified_findings={},
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _required_mapping_list(
    value: object,
    path: str,
    issues: list[ValidationIssue],
) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        issues.append(
            ValidationIssue(
                "expected_list",
                path,
                f"{path} must be a list",
            )
        )
        return []
    result: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            issues.append(
                ValidationIssue(
                    "malformed_list_item",
                    f"{path}[{index}]",
                    "list item must be an object",
                )
            )
            continue
        result.append(item)
    return result


def _required_text(
    source: Mapping[str, Any],
    field: str,
    path: str,
    issues: list[ValidationIssue],
) -> str | None:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        issues.append(
            ValidationIssue(
                "missing_text_value",
                f"{path}.{field}",
                f"{field} must be a non-blank string",
            )
        )
        return None
    return value


def _required_int(
    source: Mapping[str, Any],
    field: str,
    path: str,
    issues: list[ValidationIssue],
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> int | None:
    value = source.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        issues.append(
            ValidationIssue(
                "missing_integer_value",
                f"{path}.{field}",
                f"{field} must be an integer",
            )
        )
        return None
    if positive and value <= 0:
        issues.append(
            ValidationIssue(
                "invalid_integer_value",
                f"{path}.{field}",
                f"{field} must be positive",
            )
        )
        return None
    if nonnegative and value < 0:
        issues.append(
            ValidationIssue(
                "invalid_integer_value",
                f"{path}.{field}",
                f"{field} must be non-negative",
            )
        )
        return None
    return value


def _required_decimal(
    source: Mapping[str, Any],
    field: str,
    path: str,
    issues: list[ValidationIssue],
) -> Decimal | None:
    value = source.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        issues.append(
            ValidationIssue(
                "missing_decimal_value",
                f"{path}.{field}",
                f"{field} must be a finite number or decimal string",
            )
        )
        return None
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation:
        decimal_value = Decimal("NaN")
    if not decimal_value.is_finite():
        issues.append(
            ValidationIssue(
                "invalid_decimal_value",
                f"{path}.{field}",
                f"{field} must be finite",
            )
        )
        return None
    return decimal_value


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing validation output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--emit-gate-packets",
        type=Path,
        help="optional new directory for gate_1.json through gate_3.json",
    )
    args = parser.parse_args()
    try:
        snapshot = load_json_object(args.snapshot)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: cannot load Wave 1 validation snapshot: {exc}")
        return 2

    repository_root = Path(__file__).resolve().parents[2]
    try:
        thresholds = load_thresholds(
            repository_root / "config" / "validation_thresholds.yml"
        )
    except ValueError as exc:
        print(f"BLOCKED: cannot load validation thresholds: {exc}")
        return 2
    report = reproduce_wave1(
        snapshot,
        thresholds=thresholds,
        artifact_root=repository_root,
    )
    try:
        _write_new_json(args.output, report.to_dict())
        if args.emit_gate_packets is not None:
            for packet in report.gate_packets:
                _write_new_json(
                    args.emit_gate_packets / f"gate_{packet['gate']}.json",
                    packet,
                )
    except OSError as exc:
        print(f"BLOCKED: cannot write new validation output: {exc}")
        return 2
    print(json.dumps({"status": report.status, "output": str(args.output)}))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(_main())
