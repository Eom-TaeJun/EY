"""Deterministic repository knowledge queries with fail-closed citations.

This module is deliberately not a vector search system, an LLM, or a
natural-language SQL interface.  It exposes six governed question IDs and can
read only the exact paths jointly pinned in code and
``config/knowledge_sources.yml``.  Numerical values are copied from the
independently validated Wave 1 JSON; blocked Wave 2 evidence stays labelled
blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


CANONICAL_SOURCES: dict[str, tuple[str, str]] = {
    "source_registry": ("docs/data/source_registry.md", "approved_definition"),
    "data_dictionary": ("docs/data/data_dictionary.md", "approved_definition"),
    "signal_dictionary": (
        "docs/methodology/signal_dictionary.md",
        "approved_definition",
    ),
    "test_catalog": ("docs/validation/test_catalog.md", "approved_control"),
    "decision_ledger": (
        "docs/governance/decision_ledger.md",
        "accepted_decision",
    ),
    "issue_log": ("docs/governance/issue_log.md", "governed_issue"),
    "work_status": ("docs/governance/work_status.md", "governed_status"),
    "runbook": ("docs/wiki/runbook.md", "approved_procedure"),
    "wave1_validation": (
        "outputs/qa/validated/latest/wave1_independent_validation.json",
        "validated_internal",
    ),
    "wave2_blocked_validation": (
        "outputs/qa/validated/wave2_attempt_02/wave2_validation.json",
        "blocked",
    ),
    "wave1_claim_manifest": (
        "outputs/final/wave1_claim_manifest__W1-20260727-001.json",
        "validated_internal_publication_pending",
    ),
}

QUESTION_IDS = (
    "metric_calculation",
    "source_fields",
    "failed_test_impact",
    "report_consumers",
    "definition_rationale",
    "latest_run_changes",
)

EXPECTED_EXCLUSIONS = frozenset(
    {
        "outputs/qa/wave1_independent_validation.json",
        "outputs/qa/wave1_snapshot.json",
        "outputs/qa/attempts/**",
        "outputs/qa/validated/wave2_attempt_01/**",
        "scratch/**",
        "notebooks/**",
    }
)


class KnowledgePolicyError(ValueError):
    """Raised when a source or manifest attempts to escape the policy."""


class KnowledgeQueryError(ValueError):
    """Raised for an unknown or malformed governed query."""


class DuplicateJsonKeyError(ValueError):
    """Raised when evidence JSON contains an ambiguous duplicate key."""


@dataclass(frozen=True)
class SourceSpec:
    """One immutable allowlisted source."""

    source_id: str
    path: str
    evidence_status: str


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_non_finite(token: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {token}")


class KnowledgeQueryService:
    """Answer only the six predeclared repository questions."""

    def __init__(
        self,
        repository_root: Path,
        *,
        config_path: Path | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        default_config = self.repository_root / "config/knowledge_sources.yml"
        self.config_path = (config_path or default_config).resolve()
        self._assert_inside_root(self.config_path)
        self.sources = self._load_and_validate_manifest()
        self._json_cache: dict[str, dict[str, Any]] = {}
        self._text_cache: dict[str, str] = {}
        self._validate_evidence_contracts()

    def _load_and_validate_manifest(self) -> dict[str, SourceSpec]:
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise KnowledgePolicyError(f"cannot read knowledge manifest: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise KnowledgePolicyError("knowledge manifest must be a mapping")
        if raw.get("schema_version") != "1.0":
            raise KnowledgePolicyError("knowledge manifest schema_version must be '1.0'")
        if raw.get("policy") != "deterministic_allowlist":
            raise KnowledgePolicyError("knowledge manifest policy must be deterministic_allowlist")
        if raw.get("natural_language_sql") != "prohibited":
            raise KnowledgePolicyError("natural-language SQL must remain prohibited")
        if raw.get("numerical_authority") != "validated_artifact_only":
            raise KnowledgePolicyError("numerical authority must remain validated_artifact_only")

        raw_sources = raw.get("sources")
        if not isinstance(raw_sources, Mapping):
            raise KnowledgePolicyError("knowledge manifest sources must be a mapping")
        if set(raw_sources) != set(CANONICAL_SOURCES):
            raise KnowledgePolicyError("manifest sources must exactly equal the code allowlist")

        sources: dict[str, SourceSpec] = {}
        for source_id, (expected_path, expected_status) in CANONICAL_SOURCES.items():
            entry = raw_sources.get(source_id)
            if not isinstance(entry, Mapping):
                raise KnowledgePolicyError(f"source {source_id!r} must be a mapping")
            if set(entry) != {"path", "evidence_status"}:
                raise KnowledgePolicyError(
                    f"source {source_id!r} has unexpected manifest fields"
                )
            if entry.get("path") != expected_path:
                raise KnowledgePolicyError(
                    f"source {source_id!r} path is not code-approved"
                )
            if entry.get("evidence_status") != expected_status:
                raise KnowledgePolicyError(
                    f"source {source_id!r} evidence status is not code-approved"
                )
            path = self._resolve_relative(expected_path)
            if not path.is_file():
                raise KnowledgePolicyError(
                    f"allowlisted source does not exist: {expected_path}"
                )
            sources[source_id] = SourceSpec(
                source_id=source_id,
                path=expected_path,
                evidence_status=expected_status,
            )

        exclusions = raw.get("excluded_paths")
        if not isinstance(exclusions, list) or not all(
            isinstance(value, str) for value in exclusions
        ):
            raise KnowledgePolicyError("excluded_paths must be a list of strings")
        if frozenset(exclusions) != EXPECTED_EXCLUSIONS:
            raise KnowledgePolicyError("excluded_paths must equal the fail-closed policy")

        questions = raw.get("questions")
        if questions != list(QUESTION_IDS):
            raise KnowledgePolicyError("question IDs must exactly equal the governed list")
        return sources

    def _assert_inside_root(self, path: Path) -> None:
        try:
            path.relative_to(self.repository_root)
        except ValueError as exc:
            raise KnowledgePolicyError("path escapes the repository root") from exc

    def _resolve_relative(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise KnowledgePolicyError("absolute paths and traversal are prohibited")
        resolved = (self.repository_root / path).resolve()
        self._assert_inside_root(resolved)
        return resolved

    def resolve_source(self, source_id: str) -> Path:
        """Resolve an exact allowlisted source ID; arbitrary paths are rejected."""

        spec = self.sources.get(source_id)
        if spec is None:
            raise KnowledgePolicyError(f"source is not allowlisted: {source_id!r}")
        return self._resolve_relative(spec.path)

    def _read_text(self, source_id: str) -> str:
        if source_id not in self._text_cache:
            self._text_cache[source_id] = self.resolve_source(source_id).read_text(
                encoding="utf-8"
            )
        return self._text_cache[source_id]

    def _read_json(self, source_id: str) -> dict[str, Any]:
        if source_id not in self._json_cache:
            path = self.resolve_source(source_id)
            try:
                value = json.loads(
                    path.read_text(encoding="utf-8"),
                    object_pairs_hook=_reject_duplicate_keys,
                    parse_constant=_reject_non_finite,
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise KnowledgePolicyError(
                    f"invalid JSON evidence in {self.sources[source_id].path}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise KnowledgePolicyError("JSON evidence root must be an object")
            self._json_cache[source_id] = value
        return self._json_cache[source_id]

    def _validate_evidence_contracts(self) -> None:
        wave1 = self._read_json("wave1_validation")
        claim_manifest = self._read_json("wave1_claim_manifest")
        wave2 = self._read_json("wave2_blocked_validation")

        if wave1.get("status") != "pass" or wave1.get("issues") != []:
            raise KnowledgePolicyError("Wave 1 evidence is not independently validated")
        wave1_run = wave1.get("run_id")
        if not isinstance(wave1_run, str) or claim_manifest.get("run_id") != wave1_run:
            raise KnowledgePolicyError("Wave 1 validation and claim run IDs differ")
        expected_hash = claim_manifest.get("claims", [{}])[0].get(
            "validation_artifact_sha256"
        )
        actual_hash = hashlib.sha256(
            self.resolve_source("wave1_validation").read_bytes()
        ).hexdigest()
        if expected_hash != actual_hash:
            raise KnowledgePolicyError("Wave 1 validation hash differs from claim manifest")
        publication = claim_manifest.get("publication")
        if not isinstance(publication, Mapping) or publication.get("status") != "pending":
            raise KnowledgePolicyError("Wave 1 publication boundary is not pending")
        if claim_manifest.get("signal_definition_version") != self._wave1_version():
            raise KnowledgePolicyError("Wave 1 definition versions differ")

        if (
            wave2.get("status") != "blocked"
            or wave2.get("gate_4_eligible") is not False
            or wave2.get("approval") != "not_granted"
        ):
            raise KnowledgePolicyError("Wave 2 evidence must remain explicitly blocked")
        issues = wave2.get("issues")
        if not isinstance(issues, list) or not issues:
            raise KnowledgePolicyError("blocked Wave 2 evidence requires issue details")

    def _wave1_version(self) -> str:
        wave1 = self._read_json("wave1_validation")
        packets = wave1.get("gate_packets")
        if not isinstance(packets, list):
            raise KnowledgePolicyError("Wave 1 gate_packets must be a list")
        for packet in packets:
            if isinstance(packet, Mapping) and packet.get("gate") == 3:
                checks = packet.get("checks")
                if not isinstance(checks, list):
                    break
                for check in checks:
                    if (
                        isinstance(check, Mapping)
                        and check.get("check_id") == "definition_version"
                    ):
                        evidence = check.get("evidence")
                        if (
                            isinstance(evidence, Mapping)
                            and isinstance(evidence.get("version"), str)
                        ):
                            return evidence["version"]
        raise KnowledgePolicyError("Wave 1 definition version is missing")

    def _markdown_citation(self, source_id: str, heading: str) -> dict[str, str]:
        text = self._read_text(source_id)
        if re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, re.MULTILINE) is None:
            raise KnowledgePolicyError(
                f"citation heading {heading!r} is absent from "
                f"{self.sources[source_id].path}"
            )
        spec = self.sources[source_id]
        return {
            "path": spec.path,
            "heading": heading,
            "evidence_status": spec.evidence_status,
        }

    def _json_citation(self, source_id: str, pointer: str) -> dict[str, str]:
        self._resolve_json_pointer(self._read_json(source_id), pointer)
        spec = self.sources[source_id]
        return {
            "path": spec.path,
            "json_pointer": pointer,
            "evidence_status": spec.evidence_status,
        }

    @staticmethod
    def _resolve_json_pointer(document: object, pointer: str) -> Any:
        if not pointer.startswith("$."):
            raise KnowledgePolicyError("JSON pointer must start with '$.'")
        current = document
        for token in pointer[2:].split("."):
            match = re.fullmatch(r"([A-Za-z0-9_]+)(?:\[(\d+)\])?", token)
            if match is None:
                raise KnowledgePolicyError(f"unsupported JSON pointer token: {token}")
            key, index = match.groups()
            if not isinstance(current, Mapping) or key not in current:
                raise KnowledgePolicyError(f"JSON pointer does not resolve: {pointer}")
            current = current[key]
            if index is not None:
                if not isinstance(current, list) or int(index) >= len(current):
                    raise KnowledgePolicyError(f"JSON pointer does not resolve: {pointer}")
                current = current[int(index)]
        return current

    def _base(
        self,
        *,
        question_id: str,
        run_id: str,
        definition_version: str,
        evidence_status: str,
        answer: Mapping[str, Any],
        citations: list[dict[str, str]],
    ) -> dict[str, Any]:
        if not citations:
            raise KnowledgePolicyError("a knowledge answer cannot be source-free")
        return {
            "schema_version": "1.0",
            "question_id": question_id,
            "run_id": run_id,
            "definition_version": definition_version,
            "evidence_status": evidence_status,
            "answer": dict(answer),
            "citations": citations,
            "authority_boundary": {
                "numerical_authority": "validated_artifact_only",
                "natural_language_sql": "prohibited",
                "model_approval": "not_performed",
            },
        }

    def answer(self, question_id: str) -> dict[str, Any]:
        """Return one governed answer or fail closed for all other input."""

        handlers = {
            "metric_calculation": self._metric_calculation,
            "source_fields": self._source_fields,
            "failed_test_impact": self._failed_test_impact,
            "report_consumers": self._report_consumers,
            "definition_rationale": self._definition_rationale,
            "latest_run_changes": self._latest_run_changes,
        }
        handler = handlers.get(question_id)
        if handler is None:
            raise KnowledgeQueryError(
                f"unknown question_id {question_id!r}; allowed IDs: {', '.join(QUESTION_IDS)}"
            )
        return handler()

    def _wave1_context(self) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        wave1 = self._read_json("wave1_validation")
        claim = self._read_json("wave1_claim_manifest")
        run_id = wave1["run_id"]
        version = self._wave1_version()
        return wave1, claim, run_id, version

    def _metric_calculation(self) -> dict[str, Any]:
        wave1, claim, run_id, version = self._wave1_context()
        outcomes = wave1["verified_findings"]["risk_band_outcomes"]
        high_index = next(
            index
            for index, outcome in enumerate(outcomes)
            if outcome.get("risk_band") == "High"
        )
        high = outcomes[high_index]
        return self._base(
            question_id="metric_calculation",
            run_id=run_id,
            definition_version=version,
            evidence_status="validated_internal",
            answer={
                "metric_id": "observed_default_rate",
                "calculation": "default_count / sample_count",
                "display_rule": claim["rendering_notes"]["percentage_display"],
                "validated_example": {
                    "risk_band": high["risk_band"],
                    "sample_count": high["sample_count"],
                    "default_count": high["default_count"],
                    "observed_default_rate": high["observed_default_rate"],
                },
            },
            citations=[
                self._json_citation(
                    "wave1_claim_manifest",
                    "$.rendering_notes.percentage_display",
                ),
                self._json_citation(
                    "wave1_validation",
                    f"$.verified_findings.risk_band_outcomes[{high_index}]",
                ),
            ],
        )

    def _source_fields(self) -> dict[str, Any]:
        _, _, run_id, version = self._wave1_context()
        return self._base(
            question_id="source_fields",
            run_id=run_id,
            definition_version=version,
            evidence_status="approved_definition",
            answer={
                "signal_id": "delinquent_months_6m",
                "source_fields": [
                    "PAY_0",
                    "PAY_2",
                    "PAY_3",
                    "PAY_4",
                    "PAY_5",
                    "PAY_6",
                ],
                "core_field": "core.account_month.repayment_status",
                "transformation": "count April–September statuses > 0",
                "raw_value_policy": "source integer preserved; do not silently recode",
            },
            citations=[
                self._markdown_citation("source_registry", "Header structure"),
                self._markdown_citation("data_dictionary", "Core fields"),
                self._markdown_citation("signal_dictionary", "Signal Dictionary"),
            ],
        )

    def _failed_test_impact(self) -> dict[str, Any]:
        wave1, claim, run_id, version = self._wave1_context()
        claims = claim["claims"]
        impact_ids = [
            item["claim_id"]
            for item in claims
            if item.get("claim_id") in {"W1-CLM-002", "W1-CLM-005", "W1-CLM-006"}
        ]
        wide_to_long_check = wave1["gate_packets"][1]["checks"][2]
        if wide_to_long_check.get("check_id") != "wide_to_long_rows":
            raise KnowledgePolicyError(
                "Wave 1 wide-to-long check is absent from the governed location"
            )
        return self._base(
            question_id="failed_test_impact",
            run_id=run_id,
            definition_version=version,
            evidence_status="governed_hypothetical_impact",
            answer={
                "test_id": "DQ-003",
                "test_rule": "each borrower has six account-month rows",
                "if_failed": {
                    "affected_table": "core.account_month",
                    "affected_derived_objects": [
                        "mart.borrower_risk_signal",
                        "mart.signal_default_summary",
                        "mart.risk_band_summary",
                    ],
                    "affected_claim_ids": impact_ids,
                    "release_action": "block dependent claims until the exact wide-to-long reconciliation passes",
                },
                "latest_run_result": wide_to_long_check["status"],
            },
            citations=[
                self._markdown_citation("test_catalog", "Source and structure"),
                self._markdown_citation("data_dictionary", "Initial tables"),
                self._json_citation("wave1_claim_manifest", "$.claims"),
                self._json_citation(
                    "wave1_validation",
                    "$.gate_packets[1].checks[2]",
                ),
            ],
        )

    def _report_consumers(self) -> dict[str, Any]:
        _, claim, run_id, version = self._wave1_context()
        claim_index = next(
            index
            for index, item in enumerate(claim["claims"])
            if item.get("claim_id") == "W1-CLM-006"
        )
        selected = claim["claims"][claim_index]
        return self._base(
            question_id="report_consumers",
            run_id=run_id,
            definition_version=version,
            evidence_status="validated_internal_publication_pending",
            answer={
                "claim_id": selected["claim_id"],
                "result": selected["claim"],
                "report_type": claim["report_type"],
                "validation_artifact": selected["validation_artifact"],
                "publication": claim["publication"],
                "consumer_controls": [
                    "run-bound internal evidence report",
                    "Gate 5 and human approval before external publication",
                ],
            },
            citations=[
                self._json_citation(
                    "wave1_claim_manifest",
                    f"$.claims[{claim_index}]",
                ),
                self._json_citation("wave1_claim_manifest", "$.publication"),
                self._markdown_citation(
                    "runbook", "6. Generate an internal reader-facing report"
                ),
                self._markdown_citation(
                    "runbook", "7. Gate 5 and publication"
                ),
            ],
        )

    def _definition_rationale(self) -> dict[str, Any]:
        _, _, run_id, version = self._wave1_context()
        row = self._find_markdown_table_row("decision_ledger", "DEC-005")
        return self._base(
            question_id="definition_rationale",
            run_id=run_id,
            definition_version=version,
            evidence_status="accepted_decision",
            answer={
                "decision_id": row[0],
                "problem": row[2],
                "decision": row[4],
                "rationale": row[5],
                "reversible": row[6],
                "status": row[8],
            },
            citations=[
                self._markdown_citation("decision_ledger", "Decision Ledger"),
                self._markdown_citation(
                    "decision_ledger", "Decision impact and rollback"
                ),
            ],
        )

    def _find_markdown_table_row(self, source_id: str, first_cell: str) -> list[str]:
        for line in self._read_text(source_id).splitlines():
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and cells[0] == first_cell:
                return cells
        raise KnowledgePolicyError(
            f"table row {first_cell!r} is absent from {self.sources[source_id].path}"
        )

    def _latest_run_changes(self) -> dict[str, Any]:
        wave1, _, prior_run_id, prior_version = self._wave1_context()
        wave2 = self._read_json("wave2_blocked_validation")
        consistency_check = next(
            check
            for check in wave2["checks"]
            if check.get("check_id") == "model_run_version_consistency"
        )
        issues = [
            {"code": issue["code"], "path": issue["path"], "message": issue["message"]}
            for issue in wave2["issues"]
        ]
        return self._base(
            question_id="latest_run_changes",
            run_id=wave2["run_id"],
            definition_version=wave2["definition_version"],
            evidence_status="blocked",
            answer={
                "previous_validated_run": {
                    "run_id": prior_run_id,
                    "definition_version": prior_version,
                    "status": wave1["status"],
                },
                "latest_run": {
                    "run_id": wave2["run_id"],
                    "definition_version": wave2["definition_version"],
                    "status": wave2["status"],
                    "gate_4_eligible": wave2["gate_4_eligible"],
                    "approval": wave2["approval"],
                },
                "scope_added": consistency_check["evidence"]["models_checked"],
                "release_blockers": issues,
            },
            citations=[
                self._json_citation("wave2_blocked_validation", "$.status"),
                self._json_citation(
                    "wave2_blocked_validation", "$.definition_version"
                ),
                self._json_citation("wave2_blocked_validation", "$.issues"),
                self._json_citation(
                    "wave2_blocked_validation",
                    "$.checks[8].evidence.models_checked",
                ),
                self._markdown_citation("work_status", "Wave 2 retrospective benchmark"),
            ],
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Answer one governed repository question. This command does not "
            "accept natural-language SQL or arbitrary source paths."
        )
    )
    parser.add_argument("--question-id", choices=QUESTION_IDS)
    parser.add_argument(
        "--list-questions",
        action="store_true",
        help="print the six governed question IDs as JSON",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="repository root (defaults to current working directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.list_questions:
        print(json.dumps({"question_ids": QUESTION_IDS}, indent=2))
        return 0
    if args.question_id is None:
        parser.error("--question-id is required unless --list-questions is used")

    try:
        answer = KnowledgeQueryService(args.repository_root).answer(args.question_id)
    except (KnowledgePolicyError, KnowledgeQueryError, OSError, KeyError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
