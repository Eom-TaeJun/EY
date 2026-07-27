# Presentation Scaffold

No numerical slide is authoritative on its own. Presentation artifacts must be
generated from the same validated run and claim manifest as the internal
report, then reconciled at Gate 5.

## Current status

- deck structure: implemented;
- validated numerical slide content: pending Gate 1–3 evidence;
- cross-artifact reconciliation: pending Gate 5;
- external publication: pending human approval.

Use [`wave1_deck_outline.md`](wave1_deck_outline.md) as the page contract.
Do not replace placeholders by copying values from a terminal, database client,
README, or interview notes.

## Required metadata on every numerical page

- run ID;
- validation artifact;
- claim ID;
- signal/definition version when applicable;
- denominator and observation window;
- limitation or proxy label;
- generated timestamp.

If any metadata is missing, the page is a structure-only draft.
