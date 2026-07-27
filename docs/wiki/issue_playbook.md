# Issue Investigation Playbook

## Triage rule

Investigate from the earliest affected evidence boundary. Preserve the failing
run and stop only its dependent branch; do not hide the failure or edit the
downstream artifact.

## Unexpected jump in a risk summary

1. confirm the result run ID and definition version
2. compare PD/signal population and outcome components
3. identify concentrated segments
4. inspect downstream and upstream lineage nodes
5. check quality and reconciliation failures
6. reproduce the earliest abnormal transformation
7. record root cause and affected artifacts
8. fix upstream logic
9. rerun regression tests
10. regenerate and reconcile reports

## Report eligibility failure

If `src.reporting.build_wave1_report` returns `blocked`:

1. preserve the exact validation JSON and command output;
2. read the reported contract path or arithmetic mismatch;
3. compare the independent validation `issues`, Gate packet, and referenced
   artifact;
4. fix the upstream producer, not the report builder;
5. create a new snapshot and independent validation output;
6. rerun with a new run ID and new report filenames.

Do not manually add a missing finding, change `status`, or remove an issue from
the validation JSON.

## Impact mapping

| Earliest failure | Blocked downstream evidence |
|---|---|
| source/hash/shape | raw load, core, signals, all numerical reports |
| raw reconciliation | core and every downstream result |
| primary/foreign key or wide-to-long | signals, risk bands, models, reports |
| amount reconciliation | affected feature/signal/model/report totals |
| SQL test suite | Gate 2 and all publication claims |
| timing or leakage | signal and model interpretation |
| outcome population | observed default-rate and band claims |
| run-ID mismatch | cross-artifact comparison and Gate 5 |

Issue records should include symptom, root cause, impact scope, evidence path,
resolution, validation test, owner, run ID, definition version, and approval
status.
