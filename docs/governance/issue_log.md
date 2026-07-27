# Issue Log

This file is the canonical issue record until `audit.issue_log` is available.
After database initialization, deterministic tooling writes the same `issue_id`
to both locations; `audit.issue_log` is canonical for run-specific issues.
The Orchestrator owns status changes. Builders and reviewers may open issues but
must not delete or hide resolved history.

| Issue ID | Opened | Owner | Severity | Gate | Status | Summary | Impact | Evidence | Resolution |
|---|---|---|---|---|---|---|---|---|---|
| GOV-001 | 2026-07-27 | Orchestrator | Major | G0 | Resolved | Wave 0 lacked single-writer ownership, executable gate checks, accepted decisions, issue control, and complete role contracts | Wave 1 implementation was blocked pending governance repair | independent Reviewer audit; `make gate0` | controls added; independent Reviewer approved with Critical 0 and Major 0 |

## Status values

`Open`, `Blocked`, `In Progress`, `Resolved`, and `Accepted Risk` are allowed.
Only a human may accept a Critical or publication-related risk.
