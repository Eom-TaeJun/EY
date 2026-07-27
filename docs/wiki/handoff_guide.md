# Handoff Guide

## Handoff outcome

A new analyst can reproduce the latest internal result, trace each claim to the
source, identify what a failed Gate affects, and distinguish execution,
validation, Gate passage, and human publication approval.

## Reading order

1. [`README.md`](../../README.md) — 30-second portfolio summary and commands
2. [`PROJECT_STATE.md`](../../PROJECT_STATE.md) — current checkpoint and blockers
3. [`source_registry.md`](../data/source_registry.md) — source identity and hash
4. [`data_dictionary.md`](../data/data_dictionary.md) — relational grains
5. [`test_catalog.md`](../validation/test_catalog.md) — protected SQL controls
6. [`signal_dictionary.md`](../methodology/signal_dictionary.md) — signal definitions
7. [`wave2_validation_report.md`](../validation/wave2_validation_report.md) — model validation boundary
8. [`lineage_spec.md`](../data/lineage_spec.md) — separate lineage/economic graph contract
9. [`knowledge_query.md`](knowledge_query.md) — bounded evidence retrieval
10. [`evidence_map.md`](../final/evidence_map.md) — role capability to artifact mapping
11. [`runbook.md`](runbook.md) — execution and recovery

## Current retained packet

| Layer | Identity and status | Evidence |
|---|---|---|
| Source/Wave 1 | `W1-20260727-001`, definition `0.1.0`, Gates 1–3 pass | [independent validation](../../outputs/qa/validated/latest/wave1_independent_validation.json) |
| Office reporting | Excel/PPT/Word generated; Gate 5 mismatch 0, unresolved 0/6 | [manifest](../../outputs/final/wave1_office_manifest__W1-20260727-001.json), [Gate 5](../../outputs/qa/validated/latest/gate_5.json) |
| Publication | internal only; human approval pending; visual render `not_run` | [Office validation](../../outputs/qa/validated/wave1_office/wave1_office_validation__W1-20260727-001.json) |
| Wave 2 | `W2-PD-20260727-001`, definition `0.2.0`; numeric checks reproduced, Gate 4 blocked | [attempt 2](../../outputs/qa/validated/wave2_attempt_02/wave2_validation.json) |
| Wave 3 | separate `data_lineage`/`economic_transmission`; six allowlisted questions | [lineage contract](../data/lineage_spec.md), [query contract](knowledge_query.md) |

## Canonical versus rebuildable

| Type | Examples | Handoff rule |
|---|---|---|
| Canonical | immutable source/hash, definitions, decisions, validated run outputs | preserve history; never repair in place |
| Rebuildable data | staging/core/mart and graph registrations | rebuild from canonical source and versioned SQL |
| Rebuildable report | Markdown, Excel, PowerPoint, Word | regenerate from one validated run; never reconcile manually |
| Procedural knowledge | this Wiki and runbook | may explain process but may not supply numerical truth |

## Acceptance questions

The receiver should be able to answer from saved evidence:

- Which source hash, run, definition, and SQL produced each reported value?
- Which controls protect the borrower-month transformation and signal outcome?
- Do rows, bills, payments, claims, and Office artifacts reconcile?
- Why is Wave 2 a retrospective internal benchmark, and what blocks Gate 4?
- Which graph answers provenance and which records an economic hypothesis?
- Can the report be regenerated without editing a number?
- Is Gate 5 passed, visually reviewed, and human-approved, or only the first?

If an answer depends on memory, chat history, an arbitrary SQL prompt, or an
untraced spreadsheet cell, the handoff is incomplete.
