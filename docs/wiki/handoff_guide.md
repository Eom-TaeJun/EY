# Handoff Guide

## Handoff outcome

A new analyst should be able to reproduce the latest eligible internal result,
identify why a failed Gate blocks downstream artifacts, and distinguish
validated evidence from publication approval.

## Reading order

1. [`README.md`](../../README.md) — reader-facing purpose and entry commands
2. [`project_charter.md`](../charter/project_charter.md) — scope and non-goals
3. [`PROJECT_STATE.md`](../../PROJECT_STATE.md) — active Wave and checkpoint
4. [`source_registry.md`](../data/source_registry.md) — source identity and hash
5. [`data_dictionary.md`](../data/data_dictionary.md) — fields and tables
6. [`test_catalog.md`](../validation/test_catalog.md) — protected rules
7. [`signal_dictionary.md`](../methodology/signal_dictionary.md) — signal versions
8. [`decision_ledger.md`](../governance/decision_ledger.md) — approved assumptions
9. [`work_status.md`](../governance/work_status.md) — execution history
10. [`runbook.md`](runbook.md) — execution and recovery
11. [`evidence_map.md`](../final/evidence_map.md) — claim activation and evidence

## Canonical versus derived

| Type | Examples | Handoff rule |
|---|---|---|
| Canonical source | immutable raw file and SHA-256, approved definitions, thresholds, decision records, validated run outputs | preserve history; never repair in place |
| Rebuildable data | staging/core/mart tables | rebuild from canonical source and versioned code |
| Rebuildable report | internal Markdown, Excel, PowerPoint, Word | regenerate from one validated run; never reconcile manually |
| Procedural knowledge | this Wiki and runbook | may explain process but may not supply numerical truth |

## Minimum handoff packet

- repository commit or checkpoint identity;
- source ID and hash;
- database/runtime instructions without credentials;
- latest run ID and definition version;
- Gate 1–3 packets and independent validation result;
- failing tests and open issues, including impact;
- generated report and claim manifest, if eligible;
- explicit Gate 5 and publication status;
- exact next command.

## Acceptance questions

The receiving analyst should answer all of the following from saved evidence:

- What source and run produced the result?
- Which transformation creates each reported grain?
- Which tests protect each claim?
- Do bills, payments, rows, and outcome populations reconcile?
- What failed in the latest unsuccessful run, and what is affected?
- Can the internal report be regenerated without editing a number?
- Is the result internally validated, Gate 5 reviewed, and human-approved, or
  only one of those states?

If any answer requires memory, chat history, or a spreadsheet cell with no
producer path, the handoff is incomplete.
