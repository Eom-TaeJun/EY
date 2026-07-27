# Reconciliation Plan

## Required tie-outs

1. downloaded source rows and raw table rows
2. raw borrowers and core borrowers
3. expected and actual customer-month rows
4. wide and long bill totals by source month
5. wide and long payment totals by source month
6. SQL and Python signal summaries
7. database and exported CSV/Excel summaries
8. validated result and README/PPT numbers

## Failure procedure

- reproduce the difference
- identify source, parsing, transformation, or reporting layer
- calculate affected rows and metrics
- create an issue
- fix the earliest incorrect layer
- run regression tests
- regenerate downstream outputs

Never change the final report to match a wrong upstream number.
