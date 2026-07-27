"""Fail-closed Wave 0 governance checks.

This validator checks machine-observable controls. Independent review still
supplies the release recommendation recorded in work_status.md.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require_text(path: str, *needles: str) -> list[str]:
    target = ROOT / path
    if not target.exists():
        return [f"{path}: missing"]
    text = target.read_text(encoding="utf-8")
    return [f"{path}: missing text {needle!r}" for needle in needles if needle not in text]


def main() -> int:
    failures: list[str] = []
    failures += require_text(
        "HARNESS.md",
        "Approve or Revise",
        "Human approval required",
        "Gate 0: Governance",
    )
    failures += require_text(
        "docs/governance/task_graph.md",
        "## File ownership",
        "| Hermes |",
        "| Data Model |",
        "| SQL QA |",
        "| Risk Signal |",
        "| Risk Component |",
        "| Graph |",
        "| Validation |",
        "| Documentation |",
        "| Reviewer |",
    )
    failures += require_text(
        "docs/governance/quality_gates.md",
        "`make gate0`",
        "`make gate1`",
        "`make gate2`",
        "`make gate3`",
        "`make gate4`",
        "`make gate5`",
        "fail closed",
    )
    failures += require_text(
        "docs/governance/decision_ledger.md",
        "| DEC-001 | 2026-07-27",
        "| DEC-002 | 2026-07-27",
        "| DEC-003 | 2026-07-27",
        "| Accepted |",
        "### Decision impact and rollback",
    )
    failures += require_text(
        "docs/governance/approval_matrix.md",
        "## Separation of duties",
        "cannot recommend approval of its own gate",
    )
    failures += require_text(
        "docs/governance/issue_log.md",
        "`audit.issue_log`",
        "| GOV-001 | 2026-07-27",
    )
    failures += require_text(
        "agents/INDEX.md",
        "`risk_component.md`",
        "`graph.md`",
    )
    failures += require_text(
        "agents/hermes.md",
        "`config/data_sources.yml`",
        "`docs/data/source_registry.md`",
    )
    failures += require_text(
        "agents/graph.md",
        "`tests/graph/`",
    )
    failures += require_text(
        "Makefile",
        "gate1:",
        "gate2:",
        "gate3:",
        "gate4:",
        "gate5:",
        "scripts/check_gate.py",
    )

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(f"Governance validation passed: {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
