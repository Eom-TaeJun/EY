---
name: wave1
description: Execute the critical-path data ingestion, relational transformation, SQL QA, risk signals, and observed default summaries.
disable-model-invocation: true
---

Read the Harness, project state, Wave 1 prompt, and Hermes/Data Model/SQL QA/Risk Signal contracts.

Execute in dependency order:

1. source registration and Hermes ingestion
2. raw schema and reconciliation
3. core borrower and account-month model
4. wide-to-long row and amount tie-outs
5. SQL quality and business-rule tests
6. risk signals and explainable risk band
7. observed default summaries
8. README and evidence-map placeholders replaced only with validated values

Use independent subagents only for non-overlapping files. Stop at a failed gate and create an issue rather than bypassing it.
