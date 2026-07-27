#!/usr/bin/env python3
"""Build a Wave 1 internal report from independent validation evidence.

This module is a reader of ``wave1_independent_validation.json``. It never
queries builder tables, fills missing values, or converts a failed/blocked run
into reportable evidence. Before rendering, it independently checks Gate 1-3
packet contracts, run identity, reconciliation arithmetic, SQL-test counts,
and observed-default-rate arithmetic.

The generated report remains an internal evidence draft. Gate 5 review and
human publication approval are deliberately outside this command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.validation.gate_evidence import (
    GateEvidenceValidator,
    GateThresholds,
    load_json_object,
    load_thresholds,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FINDINGS = frozenset(
    {
        "source_rows",
        "raw_rows",
        "borrower_rows",
        "account_month_rows",
        "sql_test_count",
        "sql_failed_count",
        "signal_outcomes",
        "risk_band_outcomes",
    }
)


class ReportContractError(ValueError):
    """Raised when validation evidence is not safe to report."""


@dataclass(frozen=True)
class ReportBundle:
    """In-memory report and claim manifest after all checks pass."""

    run_id: str
    markdown: str
    manifest: Mapping[str, Any]


def build_report_bundle(
    validation: Mapping[str, Any],
    *,
    validation_path: Path,
    artifact_root: Path | None = REPOSITORY_ROOT,
) -> ReportBundle:
    """Validate independent evidence and render an internal Wave 1 report."""

    if validation.get("schema_version") != "1.0":
        raise ReportContractError("validation schema_version must equal '1.0'")
    run_id = _required_text(validation, "run_id", "$")
    generated_at = _required_text(validation, "generated_at", "$")
    if validation.get("status") != "pass":
        raise ReportContractError("validation status must equal 'pass'")
    issues = validation.get("issues")
    if issues != []:
        raise ReportContractError("a reportable validation result must have an empty issues list")

    thresholds = (
        load_thresholds(REPOSITORY_ROOT / "config/validation_thresholds.yml")
        if artifact_root is not None
        else None
    )
    packets = _index_gate_packets(
        validation.get("gate_packets"),
        run_id,
        artifact_root,
        thresholds=thresholds,
    )
    _validate_embedded_contract_reports(validation.get("contract_reports"), run_id)
    findings = _required_mapping(validation, "verified_findings", "$")
    missing_findings = sorted(REQUIRED_FINDINGS - findings.keys())
    if missing_findings:
        raise ReportContractError(
            "verified_findings is incomplete: " + ", ".join(missing_findings)
        )

    gate_1 = _index_checks(packets[1])
    gate_2 = _index_checks(packets[2])
    gate_3 = _index_checks(packets[3])
    source_evidence = _evidence(gate_1, "raw_rows_reconciled")
    shape_evidence = _evidence(gate_1, "source_shape_recorded")
    row_evidence = _evidence(gate_2, "wide_to_long_rows")
    bill_evidence = _evidence(gate_2, "bill_amounts")
    payment_evidence = _evidence(gate_2, "payment_amounts")
    test_evidence = _evidence(gate_2, "sql_test_suite")
    signal_count_evidence = _evidence(gate_3, "signal_count")
    version_evidence = _evidence(gate_3, "definition_version")
    outcome_evidence = _evidence(gate_3, "outcome_summary")

    source_rows = _positive_int(findings, "source_rows", "$.verified_findings")
    raw_rows = _positive_int(findings, "raw_rows", "$.verified_findings")
    borrower_rows = _positive_int(findings, "borrower_rows", "$.verified_findings")
    account_month_rows = _positive_int(
        findings, "account_month_rows", "$.verified_findings"
    )
    sql_test_count = _positive_int(
        findings, "sql_test_count", "$.verified_findings"
    )
    sql_failed_count = _nonnegative_int(
        findings, "sql_failed_count", "$.verified_findings"
    )

    _same("source_rows", source_rows, _positive_int(shape_evidence, "source_rows", "G1"))
    _same("source/raw rows", source_rows, raw_rows)
    _same(
        "source rows in raw reconciliation",
        source_rows,
        _positive_int(source_evidence, "source_rows", "G1"),
    )
    _same(
        "raw rows in raw reconciliation",
        raw_rows,
        _positive_int(source_evidence, "raw_rows", "G1"),
    )
    _same("raw/borrower rows", raw_rows, borrower_rows)
    _same(
        "borrower rows in Gate 2",
        borrower_rows,
        _positive_int(row_evidence, "borrower_rows", "G2"),
    )
    _same(
        "raw rows in Gate 2",
        raw_rows,
        _positive_int(row_evidence, "raw_rows", "G2"),
    )
    _same(
        "account-month rows in Gate 2",
        account_month_rows,
        _positive_int(row_evidence, "account_month_rows", "G2"),
    )
    months = _positive_int(row_evidence, "months_per_borrower", "G2")
    if months != 6:
        raise ReportContractError("Wave 1 requires exactly six account-history months")
    if account_month_rows != borrower_rows * months:
        raise ReportContractError("account_month_rows must equal borrower_rows × 6")
    _same(
        "SQL-test count",
        sql_test_count,
        _positive_int(test_evidence, "executed_count", "G2"),
    )
    _same(
        "failed SQL-test count",
        sql_failed_count,
        _nonnegative_int(test_evidence, "failed_count", "G2"),
    )
    if sql_failed_count != 0:
        raise ReportContractError("failed SQL-test count must equal zero")

    _validate_zero_difference(source_evidence, "difference", "source/raw row")
    _validate_zero_difference(row_evidence, "difference", "wide-to-long row")
    _validate_amount_evidence(bill_evidence, "bill")
    _validate_amount_evidence(payment_evidence, "payment")

    signal_count = _positive_int(signal_count_evidence, "count", "G3")
    definition_version = _required_text(version_evidence, "version", "G3")
    signal_rows = _validate_outcomes(
        findings.get("signal_outcomes"),
        group_field="bucket",
        expected_population=borrower_rows,
        require_signal_id=True,
    )
    band_rows = _validate_outcomes(
        findings.get("risk_band_outcomes"),
        group_field="risk_band",
        expected_population=borrower_rows,
        require_signal_id=False,
    )
    if len({row["signal_id"] for row in signal_rows}) != signal_count:
        raise ReportContractError(
            "verified signal-outcome coverage does not equal Gate 3 signal count"
        )
    _same(
        "signal summary row count",
        len(signal_rows),
        _positive_int(outcome_evidence, "summary_row_count", "G3"),
    )
    _same(
        "risk-band summary row count",
        len(band_rows),
        _positive_int(outcome_evidence, "risk_band_row_count", "G3"),
    )

    input_sha256 = hashlib.sha256(
        validation_path.read_bytes()
    ).hexdigest() if validation_path.exists() else None
    input_reference = _portable_reference(validation_path, REPOSITORY_ROOT)
    markdown = _render_markdown(
        run_id=run_id,
        generated_at=generated_at,
        definition_version=definition_version,
        source_rows=source_rows,
        raw_rows=raw_rows,
        borrower_rows=borrower_rows,
        account_month_rows=account_month_rows,
        months=months,
        bill_evidence=bill_evidence,
        payment_evidence=payment_evidence,
        sql_test_count=sql_test_count,
        sql_failed_count=sql_failed_count,
        signal_rows=signal_rows,
        band_rows=band_rows,
        input_reference=input_reference,
    )
    report_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    manifest = _build_manifest(
        run_id=run_id,
        generated_at=generated_at,
        definition_version=definition_version,
        input_reference=input_reference,
        input_sha256=input_sha256,
        report_sha256=report_sha256,
    )
    return ReportBundle(run_id=run_id, markdown=markdown, manifest=manifest)


def _index_gate_packets(
    value: object,
    run_id: str,
    artifact_root: Path | None,
    *,
    thresholds: GateThresholds | None,
) -> dict[int, Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ReportContractError("gate_packets must be a list")
    packets: dict[int, Mapping[str, Any]] = {}
    validator = GateEvidenceValidator(
        thresholds=thresholds,
        artifact_root=artifact_root,
    )
    for index, packet in enumerate(value):
        if not isinstance(packet, Mapping):
            raise ReportContractError(f"gate_packets[{index}] must be an object")
        gate = packet.get("gate")
        if not isinstance(gate, int) or isinstance(gate, bool) or gate not in (1, 2, 3):
            raise ReportContractError(f"gate_packets[{index}].gate must be 1, 2, or 3")
        if gate in packets:
            raise ReportContractError(f"duplicate Gate {gate} packet")
        report = validator.validate(
            packet,
            expected_gate=gate,
            expected_run_id=run_id,
        )
        if not report.valid:
            details = "; ".join(f"{issue.path}: {issue.message}" for issue in report.issues)
            raise ReportContractError(f"Gate {gate} packet is invalid: {details}")
        packets[gate] = packet
    if set(packets) != {1, 2, 3}:
        raise ReportContractError("exactly one Gate 1, Gate 2, and Gate 3 packet is required")
    return packets


def _validate_embedded_contract_reports(value: object, run_id: str) -> None:
    if not isinstance(value, list):
        raise ReportContractError("contract_reports must be a list")
    reports: dict[int, Mapping[str, Any]] = {}
    for index, report in enumerate(value):
        if not isinstance(report, Mapping):
            raise ReportContractError(f"contract_reports[{index}] must be an object")
        gate = report.get("gate")
        if not isinstance(gate, int) or isinstance(gate, bool) or gate not in (1, 2, 3):
            raise ReportContractError(f"contract_reports[{index}].gate must be 1, 2, or 3")
        if gate in reports:
            raise ReportContractError(f"duplicate Gate {gate} contract report")
        if report.get("run_id") != run_id:
            raise ReportContractError(f"Gate {gate} contract report has a different run_id")
        if report.get("valid") is not True or report.get("issues") != []:
            raise ReportContractError(f"Gate {gate} contract report is not valid")
        reports[gate] = report
    if set(reports) != {1, 2, 3}:
        raise ReportContractError("contract_reports must cover Gates 1-3 exactly")


def _index_checks(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    checks = packet.get("checks")
    if not isinstance(checks, list):
        raise ReportContractError(f"Gate {packet.get('gate')} checks must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for index, check in enumerate(checks):
        if not isinstance(check, Mapping):
            raise ReportContractError(f"Gate check {index} must be an object")
        check_id = check.get("check_id")
        if not isinstance(check_id, str) or not check_id.strip():
            raise ReportContractError(f"Gate check {index} has no check_id")
        if check_id in result:
            raise ReportContractError(f"duplicate check_id {check_id!r}")
        result[check_id] = check
    return result


def _evidence(
    checks: Mapping[str, Mapping[str, Any]],
    check_id: str,
) -> Mapping[str, Any]:
    check = checks.get(check_id)
    if check is None:
        raise ReportContractError(f"missing required check {check_id!r}")
    evidence = check.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ReportContractError(f"{check_id}.evidence must be an object")
    return evidence


def _validate_zero_difference(
    source: Mapping[str, Any],
    field: str,
    label: str,
) -> None:
    value = _required_int(source, field, label)
    if value != 0:
        raise ReportContractError(f"{label} difference must equal zero")


def _validate_amount_evidence(source: Mapping[str, Any], label: str) -> None:
    source_total = _decimal(source.get("source_total"), f"{label}.source_total")
    derived_total = _decimal(source.get("derived_total"), f"{label}.derived_total")
    difference = _decimal(source.get("difference"), f"{label}.difference")
    if derived_total - source_total != difference:
        raise ReportContractError(f"{label} amount difference is arithmetically inconsistent")


def _validate_outcomes(
    value: object,
    *,
    group_field: str,
    expected_population: int,
    require_signal_id: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ReportContractError(f"{group_field} outcome rows must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    totals: dict[str, int] = {}
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise ReportContractError(f"{group_field} outcome row {index} must be an object")
        signal_id = row.get("signal_id")
        if require_signal_id:
            if not isinstance(signal_id, str) or not signal_id.strip():
                raise ReportContractError(
                    f"{group_field} outcome row {index} requires signal_id"
                )
            population_key = signal_id
        else:
            if signal_id is not None:
                raise ReportContractError("risk-band rows must have signal_id null")
            population_key = "__risk_band__"
        group = row.get(group_field)
        if not isinstance(group, str) or not group.strip():
            raise ReportContractError(
                f"{group_field} outcome row {index} requires {group_field}"
            )
        unique_key = (population_key, group)
        if unique_key in seen:
            raise ReportContractError(f"duplicate outcome group {unique_key}")
        seen.add(unique_key)
        sample_count = _positive_int(row, "sample_count", f"{group_field}[{index}]")
        default_count = _nonnegative_int(
            row, "default_count", f"{group_field}[{index}]"
        )
        if default_count > sample_count:
            raise ReportContractError("default_count cannot exceed sample_count")
        reported_rate = _decimal(
            row.get("observed_default_rate"),
            f"{group_field}[{index}].observed_default_rate",
        )
        recomputed_rate = Decimal(default_count) / Decimal(sample_count)
        if reported_rate != recomputed_rate:
            raise ReportContractError(
                f"{group_field} outcome row {index} has inconsistent observed_default_rate"
            )
        totals[population_key] = totals.get(population_key, 0) + sample_count
        normalized.append(
            {
                "signal_id": signal_id,
                group_field: group,
                "sample_count": sample_count,
                "default_count": default_count,
                "observed_default_rate": str(recomputed_rate),
            }
        )
    for population_key, sample_total in totals.items():
        if sample_total != expected_population:
            raise ReportContractError(
                f"{population_key} outcome population {sample_total} "
                f"does not equal borrower population {expected_population}"
            )
    return normalized


def _required_mapping(
    source: Mapping[str, Any],
    field: str,
    path: str,
) -> Mapping[str, Any]:
    value = source.get(field)
    if not isinstance(value, Mapping):
        raise ReportContractError(f"{path}.{field} must be an object")
    return value


def _required_text(source: Mapping[str, Any], field: str, path: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReportContractError(f"{path}.{field} must be a non-blank string")
    return value


def _required_int(source: Mapping[str, Any], field: str, path: str) -> int:
    value = source.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReportContractError(f"{path}.{field} must be an integer")
    return value


def _positive_int(source: Mapping[str, Any], field: str, path: str) -> int:
    value = _required_int(source, field, path)
    if value <= 0:
        raise ReportContractError(f"{path}.{field} must be positive")
    return value


def _nonnegative_int(source: Mapping[str, Any], field: str, path: str) -> int:
    value = _required_int(source, field, path)
    if value < 0:
        raise ReportContractError(f"{path}.{field} must be non-negative")
    return value


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ReportContractError(f"{path} must be a finite decimal value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ReportContractError(f"{path} must be a finite decimal value") from exc
    if not result.is_finite():
        raise ReportContractError(f"{path} must be a finite decimal value")
    return result


def _same(label: str, left: object, right: object) -> None:
    if left != right:
        raise ReportContractError(f"{label} does not reconcile: {left!r} != {right!r}")


def _format_integer(value: int) -> str:
    return f"{value:,}"


def _format_decimal(value: object) -> str:
    return format(_decimal(value, "report value"), "f")


def _format_rate(value: object) -> str:
    rate = _decimal(value, "observed_default_rate")
    percent = (rate * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{percent}%"


def _render_markdown(
    *,
    run_id: str,
    generated_at: str,
    definition_version: str,
    source_rows: int,
    raw_rows: int,
    borrower_rows: int,
    account_month_rows: int,
    months: int,
    bill_evidence: Mapping[str, Any],
    payment_evidence: Mapping[str, Any],
    sql_test_count: int,
    sql_failed_count: int,
    signal_rows: Sequence[Mapping[str, Any]],
    band_rows: Sequence[Mapping[str, Any]],
    input_reference: str,
) -> str:
    signal_table = "\n".join(
        "| {signal_id} | {bucket} | {sample_count} | {default_count} | {rate} |".format(
            signal_id=row["signal_id"],
            bucket=row["bucket"],
            sample_count=_format_integer(row["sample_count"]),
            default_count=_format_integer(row["default_count"]),
            rate=_format_rate(row["observed_default_rate"]),
        )
        for row in sorted(signal_rows, key=lambda item: (item["signal_id"], item["bucket"]))
    )
    band_table = "\n".join(
        "| {risk_band} | {sample_count} | {default_count} | {rate} |".format(
            risk_band=row["risk_band"],
            sample_count=_format_integer(row["sample_count"]),
            default_count=_format_integer(row["default_count"]),
            rate=_format_rate(row["observed_default_rate"]),
        )
        for row in sorted(band_rows, key=lambda item: item["risk_band"])
    )
    return f"""# Wave 1 Internal Evidence Report

> Publication status: **Pending Gate 5 and human approval.** This report is an
> internal, reproducible evidence draft and must not be quoted as an externally
> approved portfolio result.

## Technical summary

Independent validation for run `{run_id}` passed the Gate 1–3 machine
contracts. Source-to-raw, raw-to-borrower, borrower-to-customer-month, bill,
and payment reconciliations satisfy the approved Gate contracts. All reported
values below are read from, or deterministically recomputed from,
`{input_reference}`; missing or inconsistent evidence would block generation.

## Scope and definitions

| Item | Validated scope |
|---|---|
| Run ID | `{run_id}` |
| Validation generated at | `{generated_at}` |
| Signal definition version | `{definition_version}` |
| Observation grain | borrower and borrower-month |
| History window | {months} source history months |
| Outcome | source-provided next-month default label |
| Claim type | descriptive observed association, not causal or IFRS 9 production output |

## Source and relational transformation reconcile

| Reconciliation | Source / expected | Derived / actual | Difference |
|---|---:|---:|---:|
| Source rows → raw rows | {_format_integer(source_rows)} | {_format_integer(raw_rows)} | 0 |
| Raw rows → borrowers | {_format_integer(raw_rows)} | {_format_integer(borrower_rows)} | 0 |
| Borrowers × {months} months → borrower-months | {_format_integer(borrower_rows * months)} | {_format_integer(account_month_rows)} | 0 |
| Wide bills → long bills | {_format_decimal(bill_evidence["source_total"])} | {_format_decimal(bill_evidence["derived_total"])} | {_format_decimal(bill_evidence["difference"])} |
| Wide payments → long payments | {_format_decimal(payment_evidence["source_total"])} | {_format_decimal(payment_evidence["derived_total"])} | {_format_decimal(payment_evidence["difference"])} |

The exact ties support use of the relational borrower-month layer for
downstream signal calculations. They do not by themselves establish that a
signal is predictive or suitable for model approval.

## SQL controls completed without reported failures

| Executed SQL tests | Failed SQL tests | Interpretation |
|---:|---:|---|
| {_format_integer(sql_test_count)} | {_format_integer(sql_failed_count)} | Gate 2 test-suite contract passed |

Test coverage and individual predicates remain auditable through the validation
packet, SQL test catalog, and deterministic SQL artifacts. A future code or
definition change requires a new run rather than editing this report.

## Observed default rate by signal bucket

Rates are recomputed as `default_count / sample_count` and displayed as
percentages rounded to two decimal places. They are descriptive comparisons
within this source population.

| Signal | Bucket | Sample | Defaults | Observed default rate |
|---|---|---:|---:|---:|
{signal_table}

## Observed default rate by initial risk band

Risk-band results use the same validated run and borrower denominator. The
bands are an explainable project rule, not an approved bank rating or Stage
definition.

| Risk band | Sample | Defaults | Observed default rate |
|---|---:|---:|---:|
{band_table}

## Method and traceability

The evidence path is:

`report claim → claim manifest → independent validation JSON → Gate packet
checks → deterministic SQL / source registry → raw source file and SHA-256`.

The report builder revalidates Gate 1–3 packet structure and arithmetic, rejects
duplicate or missing evidence, checks that all populations tie to borrowers,
and refuses to overwrite an existing report.

## Limitations and uncertainty

- The observed comparisons are descriptive; no causal effect is claimed.
- Public credit-card data does not establish a bank's production IFRS 9
  methodology, governance, rating, Stage, EAD, LGD, or ECL.
- Percentage display is rounded to two decimal places; counts remain the
  denominator authority.
- Gate 1–3 machine evidence does not replace Gate 5 cross-artifact review or
  human approval for external publication.
- A Markdown audit table is used instead of a chart in Wave 1 so exact
  denominators and defaults remain visible. Visual reporting is deferred until
  a validated, publication-reviewed artifact exists.

## Recommended next steps

1. Reconcile this report and its claim manifest against any Excel, PowerPoint,
   or Word artifact created from the same run ID.
2. Run Gate 5 cross-artifact checks without manually changing any value.
3. Obtain independent review and human publication approval before quoting
   numerical findings externally.

## Further questions

- Do signal directions and default-rate separations persist under time-aware or
  segment validation in Wave 2?
- Which public-data limitations prevent each prototype from representing a
  bank production process?
"""


def _build_manifest(
    *,
    run_id: str,
    generated_at: str,
    definition_version: str,
    input_reference: str,
    input_sha256: str | None,
    report_sha256: str,
) -> dict[str, Any]:
    common = {
        "run_id": run_id,
        "validation_artifact": input_reference,
        "validation_artifact_sha256": input_sha256,
        "required_gate_status": "pass",
    }
    return {
        "schema_version": "1.0",
        "report_type": "wave1_internal_evidence",
        "run_id": run_id,
        "validation_generated_at": generated_at,
        "signal_definition_version": definition_version,
        "report_sha256": report_sha256,
        "publication": {
            "status": "pending",
            "required_gate": 5,
            "human_approval_required": True,
        },
        "claims": [
            {
                "claim_id": "W1-CLM-001",
                "claim": "The registered source reconciles exactly to the raw table.",
                "json_pointers": [
                    "$.gate_packets[gate=1].checks[check_id=raw_rows_reconciled]",
                    "$.verified_findings.source_rows",
                    "$.verified_findings.raw_rows",
                ],
                **common,
            },
            {
                "claim_id": "W1-CLM-002",
                "claim": "Borrower and six-month borrower-month populations reconcile.",
                "json_pointers": [
                    "$.gate_packets[gate=2].checks[check_id=wide_to_long_rows]",
                    "$.verified_findings.borrower_rows",
                    "$.verified_findings.account_month_rows",
                ],
                **common,
            },
            {
                "claim_id": "W1-CLM-003",
                "claim": (
                    "Wide and long bill and payment totals reconcile within "
                    "the approved threshold."
                ),
                "json_pointers": [
                    "$.gate_packets[gate=2].checks[check_id=bill_amounts]",
                    "$.gate_packets[gate=2].checks[check_id=payment_amounts]",
                ],
                **common,
            },
            {
                "claim_id": "W1-CLM-004",
                "claim": "The validated SQL test suite has no failed test.",
                "json_pointers": [
                    "$.gate_packets[gate=2].checks[check_id=sql_test_suite]",
                    "$.verified_findings.sql_test_count",
                    "$.verified_findings.sql_failed_count",
                ],
                **common,
            },
            {
                "claim_id": "W1-CLM-005",
                "claim": "Signal-bucket observed default rates use reconciled populations.",
                "json_pointers": [
                    "$.gate_packets[gate=3].checks[check_id=outcome_summary]",
                    "$.verified_findings.signal_outcomes",
                ],
                **common,
            },
            {
                "claim_id": "W1-CLM-006",
                "claim": "Initial risk-band observed default rates use the same run.",
                "json_pointers": [
                    "$.gate_packets[gate=3].checks[check_id=outcome_summary]",
                    "$.verified_findings.risk_band_outcomes",
                ],
                **common,
            },
        ],
        "rendering_notes": {
            "percentage_display": "default_count / sample_count, rounded half up to 2 dp",
            "visual_omission": (
                "Wave 1 uses exact audit tables; charts remain deferred until "
                "publication-reviewed output exists."
            ),
        },
    }


def _portable_reference(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _safe_filename_token(run_id: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]", "_", run_id)
    if not token or token.startswith("."):
        token = f"run_{token.lstrip('.')}"
    return token[:128]


def _write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as target:
        target.write(content)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation",
        required=True,
        type=Path,
        help="independent Wave 1 validation JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "outputs/final",
        help="new report and manifest destination",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate report eligibility without writing derived artifacts",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validation = load_json_object(args.validation)
        bundle = build_report_bundle(
            validation,
            validation_path=args.validation,
            artifact_root=REPOSITORY_ROOT,
        )
    except (OSError, ValueError, json.JSONDecodeError, ReportContractError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2

    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "eligible_internal_draft",
                    "run_id": bundle.run_id,
                    "publication_status": "pending_gate_5_and_human_approval",
                },
                ensure_ascii=False,
            )
        )
        return 0

    token = _safe_filename_token(bundle.run_id)
    report_path = args.output_dir / f"wave1_internal_report__{token}.md"
    manifest_path = args.output_dir / f"wave1_claim_manifest__{token}.json"
    if report_path.exists() or manifest_path.exists():
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "refusing to overwrite an existing report or claim manifest",
                    "report": str(report_path),
                    "manifest": str(manifest_path),
                },
                ensure_ascii=False,
            )
        )
        return 2
    try:
        _write_new(report_path, bundle.markdown)
        _write_new(
            manifest_path,
            json.dumps(bundle.manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
    except OSError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "status": "generated_internal_draft",
                "run_id": bundle.run_id,
                "report": str(report_path),
                "manifest": str(manifest_path),
                "publication_status": "pending_gate_5_and_human_approval",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
