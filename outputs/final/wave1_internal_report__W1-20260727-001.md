# Wave 1 Internal Evidence Report

> Publication status: **Pending Gate 5 and human approval.** This report is an
> internal, reproducible evidence draft and must not be quoted as an externally
> approved portfolio result.

## Technical summary

Independent validation for run `W1-20260727-001` passed the Gate 1–3 machine
contracts. Source-to-raw, raw-to-borrower, borrower-to-customer-month, bill,
and payment reconciliations satisfy the approved Gate contracts. All reported
values below are read from, or deterministically recomputed from,
`outputs/qa/validated/latest/wave1_independent_validation.json`; missing or inconsistent evidence would block generation.

## Scope and definitions

| Item | Validated scope |
|---|---|
| Run ID | `W1-20260727-001` |
| Validation generated at | `2026-07-27T12:24:26.408112+00:00` |
| Signal definition version | `0.1.0` |
| Observation grain | borrower and borrower-month |
| History window | 6 source history months |
| Outcome | source-provided next-month default label |
| Claim type | descriptive observed association, not causal or IFRS 9 production output |

## Source and relational transformation reconcile

| Reconciliation | Source / expected | Derived / actual | Difference |
|---|---:|---:|---:|
| Source rows → raw rows | 30,000 | 30,000 | 0 |
| Raw rows → borrowers | 30,000 | 30,000 | 0 |
| Borrowers × 6 months → borrower-months | 180,000 | 180,000 | 0 |
| Wide bills → long bills | 8095850136 | 8095850136 | 0 |
| Wide payments → long payments | 949541777 | 949541777 | 0 |

The exact ties support use of the relational borrower-month layer for
downstream signal calculations. They do not by themselves establish that a
signal is predictive or suitable for model approval.

## SQL controls completed without reported failures

| Executed SQL tests | Failed SQL tests | Interpretation |
|---:|---:|---|
| 15 | 0 | Gate 2 test-suite contract passed |

Test coverage and individual predicates remain auditable through the validation
packet, SQL test catalog, and deterministic SQL artifacts. A future code or
definition change requires a new run rather than editing this report.

## Observed default rate by signal bucket

Rates are recomputed as `default_count / sample_count` and displayed as
percentages rounded to two decimal places. They are descriptive comparisons
within this source population.

| Signal | Bucket | Sample | Defaults | Observed default rate |
|---|---|---:|---:|---:|
| delinquency_deterioration | 1 | 2,080 | 669 | 32.16% |
| delinquency_deterioration | 2+ | 3,351 | 1,503 | 44.85% |
| delinquency_deterioration | <=0 | 24,569 | 4,464 | 18.17% |
| delinquent_months_6m | 0 | 19,931 | 2,334 | 11.71% |
| delinquent_months_6m | 1 | 4,426 | 1,320 | 29.82% |
| delinquent_months_6m | 2+ | 5,643 | 2,982 | 52.84% |
| latest_utilization_ratio | 0.80-<1.00 | 5,857 | 1,495 | 25.53% |
| latest_utilization_ratio | <0.80 | 22,020 | 4,503 | 20.45% |
| latest_utilization_ratio | >=1.00 | 2,123 | 638 | 30.05% |
| payment_coverage_ratio | 0.10-<0.50 | 4,332 | 953 | 22.00% |
| payment_coverage_ratio | <0.10 | 14,912 | 3,873 | 25.97% |
| payment_coverage_ratio | >=0.50 | 7,581 | 1,066 | 14.06% |
| payment_coverage_ratio | not_applicable | 3,175 | 744 | 23.43% |
| recent_bill_growth | 0-<0.25 | 4,671 | 993 | 21.26% |
| recent_bill_growth | <=0 | 13,347 | 3,447 | 25.83% |
| recent_bill_growth | >=0.25 | 8,787 | 1,415 | 16.10% |
| recent_bill_growth | not_applicable | 3,195 | 781 | 24.44% |
| recent_max_delinquency | 0 | 21,560 | 2,700 | 12.52% |
| recent_max_delinquency | 1 | 1,779 | 454 | 25.52% |
| recent_max_delinquency | 2+ | 6,661 | 3,482 | 52.27% |
| zero_payment_streak | 0 | 15,458 | 2,151 | 13.92% |
| zero_payment_streak | 1 | 8,247 | 2,752 | 33.37% |
| zero_payment_streak | 2+ | 6,295 | 1,733 | 27.53% |

## Observed default rate by initial risk band

Risk-band results use the same validated run and borrower denominator. The
bands are an explainable project rule, not an approved bank rating or Stage
definition.

| Risk band | Sample | Defaults | Observed default rate |
|---|---:|---:|---:|
| High | 6,910 | 3,549 | 51.36% |
| Low | 14,952 | 1,748 | 11.69% |
| Medium | 8,138 | 1,339 | 16.45% |

## Method and traceability

The evidence path is:

`report claim → claim manifest → independent validation JSON → Gate packet
checks → deterministic SQL / source registry → raw source file and SHA-256`.

The report builder revalidates Gate 1–3 packet structure and arithmetic, rejects
duplicate or missing evidence, checks that all populations tie to borrowers,
and refuses to overwrite an existing report.

## Limitations and uncertainty

- The observed comparisons are descriptive; no causal effect is claimed.
- Public credit-card data does not establish a bank's production IFRS 9
  methodology, governance, rating, Stage, EAD, LGD, or ECL.
- Percentage display is rounded to two decimal places; counts remain the
  denominator authority.
- Gate 1–3 machine evidence does not replace Gate 5 cross-artifact review or
  human approval for external publication.
- A Markdown audit table is used instead of a chart in Wave 1 so exact
  denominators and defaults remain visible. Visual reporting is deferred until
  a validated, publication-reviewed artifact exists.

## Recommended next steps

1. Reconcile this report and its claim manifest against any Excel, PowerPoint,
   or Word artifact created from the same run ID.
2. Run Gate 5 cross-artifact checks without manually changing any value.
3. Obtain independent review and human publication approval before quoting
   numerical findings externally.

## Further questions

- Do signal directions and default-rate separations persist under time-aware or
  segment validation in Wave 2?
- Which public-data limitations prevent each prototype from representing a
  bank production process?
