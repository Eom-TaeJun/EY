# Wave 1 Review Deck Outline

Status: structure-only. All numerical fields are `PENDING_VALIDATED_RUN`; do
not populate them manually.

| Page | Decision-relevant message | Evidence object | Claim ID | Activation |
|---:|---|---|---|---|
| 1 | The project is a controlled credit-risk data and SQL evidence workflow | charter, Harness, current state | non-numerical | implemented |
| 2 | The source is identifiable and protected from silent change | source registry, Gate 1 packet | W1-CLM-001 | Gate 1 + same run |
| 3 | The relational transformation preserves population and amounts | Gate 2 row/bill/payment checks | W1-CLM-002, W1-CLM-003 | Gates 1–2 + same run |
| 4 | SQL controls make data and calculation failures visible | test catalog, Gate 2 suite | W1-CLM-004 | Gate 2 + same run |
| 5 | Behavioral signals have explicit economic and timing definitions | signal dictionary, Gate 3 definition/timing/leakage checks | W1-CLM-005 | Gate 3 + same version |
| 6 | Observed outcomes are reported with samples and denominators | validated signal and risk-band outcomes | W1-CLM-005, W1-CLM-006 | Gate 3 + same run |
| 7 | Every claim can be traced and regenerated | claim manifest and lineage | all active claims | Gate 5 |
| 8 | Public-data and IFRS 9 boundaries remain explicit | limitations and proxy scope | non-numerical | reviewer confirmed |

## Page contract

Each activated page begins with one claim and shows its evidence next to the
interpretation. Quantitative pages use generated tables/charts plus an adjacent
plain-language explanation. Footer metadata must show run ID, claim ID,
definition version, and publication status.

## Prohibited edits

- typing or pasting a numerical result into the deck;
- mixing results from different run IDs;
- removing a failed test or limitation;
- describing a risk band as a bank rating or Stage;
- changing `pending` to `approved` without Gate 5 evidence and human approval.
