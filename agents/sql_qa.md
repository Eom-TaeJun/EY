# SQL QA Agent Contract

## Objective

Create reproducible SQL checks that detect source, transformation, domain, and business-rule issues.

## Outputs

- test catalog implementation
- quality result tables
- reconciliation queries
- failed-row samples
- affected-metric mapping

## Rules

- each query states purpose, grain, assumptions, and expected result
- distinguish error, warning, and analytical flag
- do not change source or transformation logic to make tests pass
- record tested rows, failed rows, rate, severity, run ID, and sample location
