# Issue Log

This file is the canonical issue record until `audit.issue_log` is available.
After database initialization, deterministic tooling writes the same `issue_id`
to both locations; `audit.issue_log` is canonical for run-specific issues.
The Orchestrator owns status changes. Builders and reviewers may open issues but
must not delete or hide resolved history.

| Issue ID | Opened | Owner | Severity | Gate | Status | Summary | Impact | Evidence | Resolution |
|---|---|---|---|---|---|---|---|---|---|
| GOV-001 | 2026-07-27 | Orchestrator | Major | G0 | Resolved | Wave 0 lacked single-writer ownership, executable gate checks, accepted decisions, issue control, and complete role contracts | Wave 1 implementation was blocked pending governance repair | independent Reviewer audit; `make gate0` | controls added; independent Reviewer approved with Critical 0 and Major 0 |
| ENV-001 | 2026-07-27 | Orchestrator | Medium | G1 | Resolved | Docker, psql, and local PostgreSQL were absent; sudo installation required an unavailable password | PostgreSQL execution was initially blocked | command exit 127 and sudo password prompt | unpacked PostgreSQL 16.14 under `/tmp` with Unix socket and no external listener |
| SQL-001 | 2026-07-27 | Data Model | Low | G2 | Resolved | First reconciliation attempt could not load the optional LLVM JIT library | first reconciliation transaction rolled back before evidence rows were inserted | PostgreSQL `llvmjit.so` / `libLLVM-17.so.1` error | `SET LOCAL jit=off`; calculations and thresholds unchanged |
| VAL-001 | 2026-07-27 | Validation | Medium | G3 | Resolved | Attempt 1 used inconsistent identifiers `delinquent_months` and `delinquent_months_6m` | independent validation blocked Gate 3 and reporting | `outputs/qa/wave1_independent_validation.json` | canonical ID aligned; failed evidence retained; new attempt 2 passed |
| DATA-001 | 2026-07-27 | SQL QA | Medium | G2 | Open | source values occur outside UCI-described education, marriage, and repayment code sets | categorical interpretation is limited; 120,334 customer-month rows contain undocumented repayment codes | `audit.test_result` DQ-016–018 | preserve exact values; do not impute, recode, or delete without authoritative documentation |

## Status values

`Open`, `Blocked`, `In Progress`, `Resolved`, and `Accepted Risk` are allowed.
Only a human may accept a Critical or publication-related risk.
