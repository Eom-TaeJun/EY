# Decision Ledger

| Decision ID | Date | Problem | Options considered | Decision | Rationale | Reversible | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| DEC-001 | YYYY-MM-DD | Same-day data choice | UCI vs large loan-performance data | Use UCI for Wave 1 | Faster deterministic DB and SQL evidence; retain expansion path | Yes | Human | Proposed |
| DEC-002 | YYYY-MM-DD | Graph technology | PostgreSQL metadata vs graph DB | Start with typed metadata tables | Traceability without infrastructure overhead | Yes | Human | Proposed |
| DEC-003 | YYYY-MM-DD | Initial scoring method | Rules vs complex ML | Explainable SQL rules first | Directly reviewable and reproducible | Yes | Human | Proposed |

## Required fields for new decisions

- affected files and outputs
- discarded alternatives
- approval requirement
- rollback method
- downstream nodes affected
