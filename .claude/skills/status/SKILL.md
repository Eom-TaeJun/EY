---
name: status
description: Summarize the current Wave, gates, completed evidence, blockers, file changes, and next unblocked tasks.
disable-model-invocation: true
---

Read `PROJECT_STATE.md`, `docs/governance/work_status.md`, `docs/governance/decision_ledger.md`, and open issues.

Return:

- active Wave and last checkpoint
- gates passed and failed
- verified outputs
- blockers and issue severity
- decisions awaiting approval
- next three dependency-safe tasks

Do not modify implementation files.
