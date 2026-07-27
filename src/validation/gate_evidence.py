"""Validate quality-gate JSON evidence without approving a gate.

The repository-level ``scripts/check_gate.py`` provides the public Makefile
entrypoint.  This module is the stricter independent-validation contract used
to challenge packet identity, duplicate checks, evidence shape, and arithmetic.

No missing or malformed value is coerced into a passing value.  Numeric
tolerances are supplied from ``config/validation_thresholds.yml`` by the caller;
the defaults below mirror version 0.1.0 and are not inferred from evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


GATE_REQUIRED_CHECKS: dict[int, frozenset[str]] = {
    1: frozenset(
        {
            "source_registered",
            "sha256_recorded",
            "source_shape_recorded",
            "raw_rows_reconciled",
        }
    ),
    2: frozenset(
        {
            "primary_key",
            "foreign_key",
            "wide_to_long_rows",
            "bill_amounts",
            "payment_amounts",
            "code_domains",
            "sql_test_suite",
        }
    ),
    3: frozenset(
        {
            "signal_count",
            "definition_version",
            "observation_timing",
            "leakage",
            "outcome_summary",
            "sql_reproducibility",
        }
    ),
    4: frozenset(
        {
            "time_validation",
            "calibration",
            "segment_stability",
            "sensitivity_direction",
            "proxy_labels",
        }
    ),
    5: frozenset(
        {
            "shared_run_id",
            "cross_artifact_values",
            "limitations",
            "evidence_map",
        }
    ),
}

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_CHECK_STATUSES = frozenset({"pass", "fail", "blocked", "not_run"})


@dataclass(frozen=True)
class GateThresholds:
    """Immutable validation thresholds controlled outside the evidence packet."""

    row_count_difference: int = 0
    floating_amount_tolerance: Decimal = Decimal("0.01")
    primary_key_duplicate_count: int = 0
    missing_required_field_count: int = 0
    minimum_signal_count: int = 5
    minimum_sql_test_count: int = 12


@dataclass(frozen=True)
class ValidationIssue:
    """One machine-readable contract or evidence failure."""

    code: str
    path: str
    message: str


@dataclass(frozen=True)
class GateContractReport:
    """Result of validating one packet; ``valid`` is release eligibility."""

    gate: int | None
    run_id: str | None
    valid: bool
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "run_id": self.run_id,
            "valid": self.valid,
            "issues": [asdict(issue) for issue in self.issues],
        }


class DuplicateJsonKeyError(ValueError):
    """Raised when a JSON object contains a duplicate key."""


def load_thresholds(path: Path) -> GateThresholds:
    """Load immutable Gate 1-3 thresholds from the canonical YAML file."""

    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read validation threshold configuration: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError("validation threshold configuration must be a mapping")
    reconciliation = value.get("reconciliation")
    quality = value.get("quality")
    if not isinstance(reconciliation, Mapping) or not isinstance(quality, Mapping):
        raise ValueError("threshold configuration requires reconciliation and quality mappings")
    row_difference = _config_int(
        reconciliation, "row_count_difference", nonnegative=True
    )
    amount_tolerance = _config_decimal(
        reconciliation, "floating_amount_tolerance", nonnegative=True
    )
    primary_key_duplicates = _config_int(
        quality, "primary_key_duplicate_count", nonnegative=True
    )
    missing_required = _config_int(
        quality, "missing_required_field_count", nonnegative=True
    )
    return GateThresholds(
        row_count_difference=row_difference,
        floating_amount_tolerance=amount_tolerance,
        primary_key_duplicate_count=primary_key_duplicates,
        missing_required_field_count=missing_required,
    )


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite(token: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {token}")


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object while rejecting duplicate keys and non-finite numbers."""

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite,
    )
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


class GateEvidenceValidator:
    """Validate packet structure and gate-specific evidence semantics."""

    def __init__(
        self,
        thresholds: GateThresholds | None = None,
        *,
        artifact_root: Path | None = None,
    ) -> None:
        self.thresholds = thresholds or GateThresholds()
        self.artifact_root = artifact_root.resolve() if artifact_root is not None else None

    def validate(
        self,
        packet: object,
        *,
        expected_gate: int | None = None,
        expected_run_id: str | None = None,
    ) -> GateContractReport:
        issues: list[ValidationIssue] = []
        if not isinstance(packet, Mapping):
            issues.append(
                ValidationIssue("packet_not_object", "$", "gate packet must be a JSON object")
            )
            return GateContractReport(None, None, False, tuple(issues))

        gate_value = packet.get("gate")
        gate = gate_value if _is_int(gate_value) and gate_value in GATE_REQUIRED_CHECKS else None
        if gate is None:
            issues.append(
                ValidationIssue("invalid_gate", "$.gate", "gate must be an integer from 1 to 5")
            )
        elif expected_gate is not None and gate != expected_gate:
            issues.append(
                ValidationIssue(
                    "unexpected_gate",
                    "$.gate",
                    f"gate {gate} does not match expected gate {expected_gate}",
                )
            )

        if packet.get("schema_version") != "1.0":
            issues.append(
                ValidationIssue(
                    "unsupported_schema_version",
                    "$.schema_version",
                    "schema_version must equal '1.0'",
                )
            )

        run_id_value = packet.get("run_id")
        run_id = run_id_value if isinstance(run_id_value, str) else None
        if run_id is None or _RUN_ID_PATTERN.fullmatch(run_id) is None:
            issues.append(
                ValidationIssue(
                    "invalid_run_id",
                    "$.run_id",
                    "run_id must be a non-blank stable identifier (3-128 safe characters)",
                )
            )
        elif expected_run_id is not None and run_id != expected_run_id:
            issues.append(
                ValidationIssue(
                    "unexpected_run_id",
                    "$.run_id",
                    f"run_id {run_id!r} does not match expected run_id {expected_run_id!r}",
                )
            )

        self._validate_timestamp(packet.get("generated_at"), issues)
        self._validate_producer(packet.get("producer"), issues)

        packet_status = packet.get("status")
        if packet_status != "pass":
            issues.append(
                ValidationIssue(
                    "gate_not_pass",
                    "$.status",
                    "status must equal 'pass'; failed, blocked, and unrun gates are not releasable",
                )
            )

        checks = packet.get("checks")
        by_id = self._index_checks(checks, issues)
        if gate is not None:
            missing = sorted(GATE_REQUIRED_CHECKS[gate] - by_id.keys())
            for check_id in missing:
                issues.append(
                    ValidationIssue(
                        "missing_required_check",
                        "$.checks",
                        f"required Gate {gate} check is missing: {check_id}",
                    )
                )

        for check_id, check in by_id.items():
            status = check.get("status")
            if status not in _ALLOWED_CHECK_STATUSES:
                issues.append(
                    ValidationIssue(
                        "invalid_check_status",
                        f"$.checks[{check_id}].status",
                        f"status must be one of {sorted(_ALLOWED_CHECK_STATUSES)}",
                    )
                )
            if status != "pass":
                issues.append(
                    ValidationIssue(
                        "check_not_pass",
                        f"$.checks[{check_id}].status",
                        "every recorded check must pass before the gate can pass",
                    )
                )
            evidence = check.get("evidence")
            if not isinstance(evidence, Mapping) or not evidence:
                issues.append(
                    ValidationIssue(
                        "invalid_evidence",
                        f"$.checks[{check_id}].evidence",
                        "evidence must be a non-empty JSON object",
                    )
                )
            elif not _contains_only_finite_numbers(evidence):
                issues.append(
                    ValidationIssue(
                        "non_finite_evidence",
                        f"$.checks[{check_id}].evidence",
                        "evidence contains a non-finite numeric value",
                    )
                )

        if gate is not None:
            self._validate_gate_semantics(gate, by_id, run_id, issues)
            self._validate_artifact_references(gate, by_id, issues)

        return GateContractReport(gate, run_id, not issues, tuple(issues))

    def _validate_artifact_references(
        self,
        gate: int,
        checks: Mapping[str, Mapping[str, Any]],
        issues: list[ValidationIssue],
    ) -> None:
        if self.artifact_root is None:
            return
        references: tuple[tuple[str, str], ...] = ()
        if gate == 1:
            references = (("source_registered", "registry_path"),)
        elif gate == 3:
            references = (("sql_reproducibility", "query_manifest"),)
        for check_id, field in references:
            value = _evidence(checks, check_id).get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            relative = Path(value)
            if relative.is_absolute():
                _semantic_issue(
                    issues,
                    check_id,
                    field,
                    f"{field} must be a repository-relative path",
                )
                continue
            resolved = (self.artifact_root / relative).resolve()
            try:
                resolved.relative_to(self.artifact_root)
            except ValueError:
                _semantic_issue(
                    issues,
                    check_id,
                    field,
                    f"{field} escapes the repository root",
                )
                continue
            if not resolved.is_file():
                issues.append(
                    ValidationIssue(
                        "missing_artifact",
                        f"$.checks[{check_id}].evidence.{field}",
                        f"referenced artifact does not exist: {value}",
                    )
                )

    def _validate_timestamp(
        self, value: object, issues: list[ValidationIssue]
    ) -> None:
        if not isinstance(value, str):
            issues.append(
                ValidationIssue(
                    "missing_generated_at",
                    "$.generated_at",
                    "generated_at must be an ISO-8601 timestamp with timezone",
                )
            )
            return
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            timestamp = None
        if timestamp is None or timestamp.tzinfo is None:
            issues.append(
                ValidationIssue(
                    "invalid_generated_at",
                    "$.generated_at",
                    "generated_at must be an ISO-8601 timestamp with timezone",
                )
            )

    def _validate_producer(
        self, value: object, issues: list[ValidationIssue]
    ) -> None:
        if not isinstance(value, Mapping):
            issues.append(
                ValidationIssue(
                    "missing_producer",
                    "$.producer",
                    "producer must identify the role and deterministic command",
                )
            )
            return
        for field in ("role", "command"):
            item = value.get(field)
            if not isinstance(item, str) or not item.strip():
                issues.append(
                    ValidationIssue(
                        "invalid_producer",
                        f"$.producer.{field}",
                        f"producer.{field} must be a non-blank string",
                    )
                )

    def _index_checks(
        self, checks: object, issues: list[ValidationIssue]
    ) -> dict[str, Mapping[str, Any]]:
        if not isinstance(checks, list):
            issues.append(
                ValidationIssue("checks_not_list", "$.checks", "checks must be a JSON list")
            )
            return {}
        by_id: dict[str, Mapping[str, Any]] = {}
        for index, value in enumerate(checks):
            path = f"$.checks[{index}]"
            if not isinstance(value, Mapping):
                issues.append(
                    ValidationIssue("check_not_object", path, "each check must be an object")
                )
                continue
            check_id = value.get("check_id")
            if not isinstance(check_id, str) or not check_id.strip():
                issues.append(
                    ValidationIssue(
                        "invalid_check_id", f"{path}.check_id", "check_id must be non-blank"
                    )
                )
                continue
            if check_id in by_id:
                issues.append(
                    ValidationIssue(
                        "duplicate_check_id",
                        f"{path}.check_id",
                        f"duplicate check_id is forbidden: {check_id}",
                    )
                )
                continue
            by_id[check_id] = value
        return by_id

    def _validate_gate_semantics(
        self,
        gate: int,
        checks: Mapping[str, Mapping[str, Any]],
        run_id: str | None,
        issues: list[ValidationIssue],
    ) -> None:
        if gate == 1:
            self._validate_gate_1(checks, issues)
        elif gate == 2:
            self._validate_gate_2(checks, issues)
        elif gate == 3:
            self._validate_gate_3(checks, issues)
        elif gate == 4:
            self._validate_gate_4(checks, issues)
        elif gate == 5:
            self._validate_gate_5(checks, run_id, issues)

    def _validate_gate_1(
        self,
        checks: Mapping[str, Mapping[str, Any]],
        issues: list[ValidationIssue],
    ) -> None:
        registered = _evidence(checks, "source_registered")
        _require_true(registered, "registered", "source_registered", issues)
        _require_nonblank(registered, "source_id", "source_registered", issues)
        _require_artifact(registered, "registry_path", "source_registered", issues)

        sha = _evidence(checks, "sha256_recorded").get("sha256")
        if not isinstance(sha, str) or _SHA256_PATTERN.fullmatch(sha) is None:
            _semantic_issue(
                issues, "sha256_recorded", "sha256", "sha256 must contain exactly 64 hex digits"
            )

        shape = _evidence(checks, "source_shape_recorded")
        shape_rows = _require_positive_int(
            shape, "source_rows", "source_shape_recorded", issues
        )
        _require_positive_int(shape, "source_columns", "source_shape_recorded", issues)

        reconciliation = _evidence(checks, "raw_rows_reconciled")
        source_rows = _require_nonnegative_int(
            reconciliation, "source_rows", "raw_rows_reconciled", issues
        )
        raw_rows = _require_nonnegative_int(
            reconciliation, "raw_rows", "raw_rows_reconciled", issues
        )
        difference = _require_int(
            reconciliation, "difference", "raw_rows_reconciled", issues
        )
        unlogged_rejects = _require_nonnegative_int(
            reconciliation, "unlogged_rejects", "raw_rows_reconciled", issues
        )
        if source_rows is not None and raw_rows is not None and source_rows != raw_rows:
            _semantic_issue(
                issues,
                "raw_rows_reconciled",
                "raw_rows",
                "raw_rows must exactly equal source_rows",
            )
        if shape_rows is not None and source_rows is not None and shape_rows != source_rows:
            _semantic_issue(
                issues,
                "raw_rows_reconciled",
                "source_rows",
                "reconciliation source_rows must match source_shape_recorded source_rows",
            )
        if difference is not None and difference != self.thresholds.row_count_difference:
            _semantic_issue(
                issues,
                "raw_rows_reconciled",
                "difference",
                f"difference must equal configured threshold {self.thresholds.row_count_difference}",
            )
        if unlogged_rejects not in (None, 0):
            _semantic_issue(
                issues,
                "raw_rows_reconciled",
                "unlogged_rejects",
                "unlogged_rejects must equal zero",
            )

    def _validate_gate_2(
        self,
        checks: Mapping[str, Mapping[str, Any]],
        issues: list[ValidationIssue],
    ) -> None:
        primary_key = _evidence(checks, "primary_key")
        duplicates = _require_nonnegative_int(
            primary_key, "duplicate_count", "primary_key", issues
        )
        null_keys = _require_nonnegative_int(
            primary_key, "null_key_count", "primary_key", issues
        )
        account_month_duplicates = _require_nonnegative_int(
            primary_key, "account_month_duplicate_count", "primary_key", issues
        )
        if duplicates not in (None, self.thresholds.primary_key_duplicate_count):
            _semantic_issue(
                issues,
                "primary_key",
                "duplicate_count",
                "duplicate_count exceeds the configured threshold",
            )
        if null_keys not in (None, self.thresholds.missing_required_field_count):
            _semantic_issue(
                issues,
                "primary_key",
                "null_key_count",
                "null_key_count exceeds the configured threshold",
            )
        if account_month_duplicates not in (
            None,
            self.thresholds.primary_key_duplicate_count,
        ):
            _semantic_issue(
                issues,
                "primary_key",
                "account_month_duplicate_count",
                "account_month_duplicate_count exceeds the configured threshold",
            )

        foreign_key = _evidence(checks, "foreign_key")
        orphan_count = _require_nonnegative_int(
            foreign_key, "orphan_count", "foreign_key", issues
        )
        if orphan_count not in (None, 0):
            _semantic_issue(
                issues, "foreign_key", "orphan_count", "orphan_count must equal zero"
            )

        rows = _evidence(checks, "wide_to_long_rows")
        borrower_rows = _require_positive_int(
            rows, "borrower_rows", "wide_to_long_rows", issues
        )
        raw_rows = _require_positive_int(
            rows, "raw_rows", "wide_to_long_rows", issues
        )
        months = _require_positive_int(
            rows, "months_per_borrower", "wide_to_long_rows", issues
        )
        expected_rows = _require_positive_int(
            rows, "expected_account_month_rows", "wide_to_long_rows", issues
        )
        actual_rows = _require_positive_int(
            rows, "account_month_rows", "wide_to_long_rows", issues
        )
        difference = _require_int(rows, "difference", "wide_to_long_rows", issues)
        if months not in (None, 6):
            _semantic_issue(
                issues,
                "wide_to_long_rows",
                "months_per_borrower",
                "the approved Wave 1 source requires exactly six months",
            )
        if raw_rows is not None and borrower_rows is not None and raw_rows != borrower_rows:
            _semantic_issue(
                issues,
                "wide_to_long_rows",
                "borrower_rows",
                "borrower_rows must exactly equal raw_rows",
            )
        if borrower_rows is not None and months is not None and expected_rows is not None:
            if borrower_rows * months != expected_rows:
                _semantic_issue(
                    issues,
                    "wide_to_long_rows",
                    "expected_account_month_rows",
                    "expected rows must equal borrower_rows × months_per_borrower",
                )
        if expected_rows is not None and actual_rows is not None and expected_rows != actual_rows:
            _semantic_issue(
                issues,
                "wide_to_long_rows",
                "account_month_rows",
                "actual and expected account-month rows must match",
            )
        if difference is not None and difference != self.thresholds.row_count_difference:
            _semantic_issue(
                issues,
                "wide_to_long_rows",
                "difference",
                "row-count difference exceeds the configured threshold",
            )

        self._validate_amount_check(checks, "bill_amounts", issues)
        self._validate_amount_check(checks, "payment_amounts", issues)

        domains = _evidence(checks, "code_domains")
        invalid_count = _require_nonnegative_int(
            domains, "invalid_count", "code_domains", issues
        )
        missing_required = _require_nonnegative_int(
            domains, "missing_required_count", "code_domains", issues
        )
        if invalid_count not in (None, 0):
            _semantic_issue(
                issues, "code_domains", "invalid_count", "invalid_count must equal zero"
            )
        if missing_required not in (None, self.thresholds.missing_required_field_count):
            _semantic_issue(
                issues,
                "code_domains",
                "missing_required_count",
                "missing_required_count exceeds the configured threshold",
            )

        suite = _evidence(checks, "sql_test_suite")
        executed = _require_nonnegative_int(
            suite, "executed_count", "sql_test_suite", issues
        )
        failed = _require_nonnegative_int(
            suite, "failed_count", "sql_test_suite", issues
        )
        if executed is not None and executed < self.thresholds.minimum_sql_test_count:
            _semantic_issue(
                issues,
                "sql_test_suite",
                "executed_count",
                f"at least {self.thresholds.minimum_sql_test_count} SQL tests are required",
            )
        if failed not in (None, 0):
            _semantic_issue(
                issues, "sql_test_suite", "failed_count", "failed_count must equal zero"
            )

    def _validate_amount_check(
        self,
        checks: Mapping[str, Mapping[str, Any]],
        check_id: str,
        issues: list[ValidationIssue],
    ) -> None:
        evidence = _evidence(checks, check_id)
        source_total = _require_decimal(evidence, "source_total", check_id, issues)
        derived_total = _require_decimal(evidence, "derived_total", check_id, issues)
        reported_difference = _require_decimal(evidence, "difference", check_id, issues)
        if source_total is None or derived_total is None or reported_difference is None:
            return
        recomputed = derived_total - source_total
        if recomputed != reported_difference:
            _semantic_issue(
                issues,
                check_id,
                "difference",
                "reported difference does not equal derived_total - source_total",
            )
        if abs(recomputed) > self.thresholds.floating_amount_tolerance:
            _semantic_issue(
                issues,
                check_id,
                "difference",
                "absolute amount difference exceeds configured tolerance "
                f"{self.thresholds.floating_amount_tolerance}",
            )

    def _validate_gate_3(
        self,
        checks: Mapping[str, Mapping[str, Any]],
        issues: list[ValidationIssue],
    ) -> None:
        count = _require_nonnegative_int(
            _evidence(checks, "signal_count"), "count", "signal_count", issues
        )
        if count is not None and count < self.thresholds.minimum_signal_count:
            _semantic_issue(
                issues,
                "signal_count",
                "count",
                f"at least {self.thresholds.minimum_signal_count} signals are required",
            )
        _require_nonblank(
            _evidence(checks, "definition_version"),
            "version",
            "definition_version",
            issues,
        )
        for check_id in ("observation_timing", "leakage"):
            evidence = _evidence(checks, check_id)
            reviewed = _require_nonnegative_int(evidence, "reviewed_count", check_id, issues)
            violations = _require_nonnegative_int(
                evidence, "violation_count", check_id, issues
            )
            if reviewed is not None and reviewed < self.thresholds.minimum_signal_count:
                _semantic_issue(
                    issues,
                    check_id,
                    "reviewed_count",
                    f"at least {self.thresholds.minimum_signal_count} signals must be reviewed",
                )
            if count is not None and reviewed is not None and reviewed != count:
                _semantic_issue(
                    issues,
                    check_id,
                    "reviewed_count",
                    "reviewed_count must equal the versioned signal count",
                )
            if violations not in (None, 0):
                _semantic_issue(
                    issues, check_id, "violation_count", "violation_count must equal zero"
                )

        summary = _evidence(checks, "outcome_summary")
        summary_rows = _require_nonnegative_int(
            summary, "summary_row_count", "outcome_summary", issues
        )
        covered = _require_nonnegative_int(
            summary, "signals_with_summary", "outcome_summary", issues
        )
        invalid = _require_nonnegative_int(
            summary, "invalid_summary_count", "outcome_summary", issues
        )
        risk_band_rows = _require_nonnegative_int(
            summary, "risk_band_row_count", "outcome_summary", issues
        )
        portfolio_defaults = _require_nonnegative_int(
            summary, "portfolio_default_count", "outcome_summary", issues
        )
        risk_band_defaults = _require_nonnegative_int(
            summary, "risk_band_default_count", "outcome_summary", issues
        )
        if summary_rows == 0:
            _semantic_issue(
                issues,
                "outcome_summary",
                "summary_row_count",
                "at least one signal outcome row is required",
            )
        if covered is not None and covered < self.thresholds.minimum_signal_count:
            _semantic_issue(
                issues,
                "outcome_summary",
                "signals_with_summary",
                f"at least {self.thresholds.minimum_signal_count} signals need outcome summaries",
            )
        if count is not None and covered is not None and covered != count:
            _semantic_issue(
                issues,
                "outcome_summary",
                "signals_with_summary",
                "signals_with_summary must equal the versioned signal count",
            )
        if invalid not in (None, 0):
            _semantic_issue(
                issues,
                "outcome_summary",
                "invalid_summary_count",
                "invalid_summary_count must equal zero",
            )
        if risk_band_rows == 0:
            _semantic_issue(
                issues,
                "outcome_summary",
                "risk_band_row_count",
                "risk-band sample counts and observed default rates are required",
            )
        if (
            portfolio_defaults is not None
            and risk_band_defaults is not None
            and portfolio_defaults != risk_band_defaults
        ):
            _semantic_issue(
                issues,
                "outcome_summary",
                "risk_band_default_count",
                "signal and risk-band summaries must contain the same total defaults",
            )

        reproducibility = _evidence(checks, "sql_reproducibility")
        reproduced = _require_nonnegative_int(
            reproducibility, "reproducible_signal_count", "sql_reproducibility", issues
        )
        unreproduced = _require_nonnegative_int(
            reproducibility, "unreproducible_count", "sql_reproducibility", issues
        )
        _require_artifact(
            reproducibility, "query_manifest", "sql_reproducibility", issues
        )
        if reproduced is not None and reproduced < self.thresholds.minimum_signal_count:
            _semantic_issue(
                issues,
                "sql_reproducibility",
                "reproducible_signal_count",
                f"at least {self.thresholds.minimum_signal_count} signals need deterministic SQL",
            )
        if count is not None and reproduced is not None and reproduced != count:
            _semantic_issue(
                issues,
                "sql_reproducibility",
                "reproducible_signal_count",
                "reproducible_signal_count must equal the versioned signal count",
            )
        if unreproduced not in (None, 0):
            _semantic_issue(
                issues,
                "sql_reproducibility",
                "unreproducible_count",
                "unreproducible_count must equal zero",
            )

    def _validate_gate_4(
        self,
        checks: Mapping[str, Mapping[str, Any]],
        issues: list[ValidationIssue],
    ) -> None:
        for check_id in (
            "time_validation",
            "calibration",
            "segment_stability",
            "sensitivity_direction",
        ):
            _require_true(_evidence(checks, check_id), "completed", check_id, issues)
        missing = _require_nonnegative_int(
            _evidence(checks, "proxy_labels"),
            "missing_label_count",
            "proxy_labels",
            issues,
        )
        if missing not in (None, 0):
            _semantic_issue(
                issues, "proxy_labels", "missing_label_count", "missing_label_count must be zero"
            )

    def _validate_gate_5(
        self,
        checks: Mapping[str, Mapping[str, Any]],
        run_id: str | None,
        issues: list[ValidationIssue],
    ) -> None:
        shared = _evidence(checks, "shared_run_id")
        distinct = _require_nonnegative_int(
            shared, "distinct_run_id_count", "shared_run_id", issues
        )
        shared_value = shared.get("run_id")
        if distinct not in (None, 1):
            _semantic_issue(
                issues,
                "shared_run_id",
                "distinct_run_id_count",
                "all artifacts must share exactly one run_id",
            )
        if run_id is not None and shared_value != run_id:
            _semantic_issue(
                issues,
                "shared_run_id",
                "run_id",
                "artifact run_id must match the packet run_id",
            )
        mismatches = _require_nonnegative_int(
            _evidence(checks, "cross_artifact_values"),
            "mismatch_count",
            "cross_artifact_values",
            issues,
        )
        if mismatches not in (None, 0):
            _semantic_issue(
                issues,
                "cross_artifact_values",
                "mismatch_count",
                "cross-artifact mismatch_count must equal zero",
            )
        _require_true(
            _evidence(checks, "limitations"), "documented", "limitations", issues
        )
        unresolved = _require_nonnegative_int(
            _evidence(checks, "evidence_map"),
            "unresolved_claim_count",
            "evidence_map",
            issues,
        )
        if unresolved not in (None, 0):
            _semantic_issue(
                issues,
                "evidence_map",
                "unresolved_claim_count",
                "unresolved_claim_count must equal zero",
            )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _config_int(
    section: Mapping[str, Any], field: str, *, nonnegative: bool
) -> int:
    value = section.get(field)
    if not _is_int(value):
        raise ValueError(f"threshold {field} must be an integer")
    if nonnegative and value < 0:
        raise ValueError(f"threshold {field} must be non-negative")
    return value


def _config_decimal(
    section: Mapping[str, Any], field: str, *, nonnegative: bool
) -> Decimal:
    value = section.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"threshold {field} must be a finite number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"threshold {field} must be a finite number") from exc
    if not result.is_finite() or (nonnegative and result < 0):
        raise ValueError(f"threshold {field} must be a non-negative finite number")
    return result


def _contains_only_finite_numbers(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(_contains_only_finite_numbers(item) for item in value.values())
    if isinstance(value, list):
        return all(_contains_only_finite_numbers(item) for item in value)
    return True


def _evidence(
    checks: Mapping[str, Mapping[str, Any]], check_id: str
) -> Mapping[str, Any]:
    check = checks.get(check_id)
    if not isinstance(check, Mapping):
        return {}
    evidence = check.get("evidence")
    return evidence if isinstance(evidence, Mapping) else {}


def _semantic_issue(
    issues: list[ValidationIssue], check_id: str, field: str, message: str
) -> None:
    issues.append(
        ValidationIssue(
            "invalid_semantic_evidence",
            f"$.checks[{check_id}].evidence.{field}",
            message,
        )
    )


def _require_true(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> None:
    if evidence.get(field) is not True:
        _semantic_issue(issues, check_id, field, f"{field} must be true")


def _require_nonblank(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> None:
    value = evidence.get(field)
    if not isinstance(value, str) or not value.strip():
        _semantic_issue(issues, check_id, field, f"{field} must be a non-blank string")


def _require_artifact(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> None:
    value = evidence.get(field)
    if not isinstance(value, str) or not value.strip() or value.strip() in {"TBD", "N/A"}:
        _semantic_issue(
            issues,
            check_id,
            field,
            f"{field} must identify a concrete repository artifact",
        )


def _require_int(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> int | None:
    value = evidence.get(field)
    if not _is_int(value):
        _semantic_issue(issues, check_id, field, f"{field} must be an integer")
        return None
    return value


def _require_nonnegative_int(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> int | None:
    value = _require_int(evidence, field, check_id, issues)
    if value is not None and value < 0:
        _semantic_issue(issues, check_id, field, f"{field} must be non-negative")
        return None
    return value


def _require_positive_int(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> int | None:
    value = _require_int(evidence, field, check_id, issues)
    if value is not None and value <= 0:
        _semantic_issue(issues, check_id, field, f"{field} must be positive")
        return None
    return value


def _require_decimal(
    evidence: Mapping[str, Any],
    field: str,
    check_id: str,
    issues: list[ValidationIssue],
) -> Decimal | None:
    value = evidence.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        _semantic_issue(
            issues, check_id, field, f"{field} must be a finite JSON number or decimal string"
        )
        return None
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation:
        decimal_value = Decimal("NaN")
    if not decimal_value.is_finite():
        _semantic_issue(issues, check_id, field, f"{field} must be finite")
        return None
    return decimal_value


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--gate", type=int, choices=range(1, 6))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        packet = load_json_object(args.packet)
        thresholds = load_thresholds(
            repository_root / "config" / "validation_thresholds.yml"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    report = GateEvidenceValidator(
        thresholds,
        artifact_root=repository_root,
    ).validate(
        packet,
        expected_gate=args.gate,
        expected_run_id=args.run_id,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(_main())
