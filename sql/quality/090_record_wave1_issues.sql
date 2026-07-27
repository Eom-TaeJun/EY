/*
Purpose:
  Preserve material Wave 1 environment, execution, validation, and source-code
  issues after independent Gate review.
Input tables:
  audit.pipeline_run and run evidence under outputs/qa/.
Output definition:
  Four immutable issue identities in audit.issue_log. Re-execution verifies
  identity through primary-key conflict rather than overwriting history.
Observation point:
  Run W1-20260727-001 and its 2026-07-27 execution attempts.
Key assumptions:
  Source-domain warnings are not repaired or assigned new business meanings.
Validation:
  Compare with docs/governance/issue_log.md and audit.test_result DQ-016–018.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=...'
  \quit 2
\endif

INSERT INTO audit.issue_log (
    issue_id,
    owner,
    severity,
    gate,
    status,
    summary,
    impact,
    evidence,
    resolution,
    pipeline_run_id
)
VALUES
    (
        'ENV-001',
        'Orchestrator',
        'Medium',
        'G1',
        'Resolved',
        'Docker, psql, and local PostgreSQL were absent; sudo installation required an unavailable password.',
        'PostgreSQL execution was initially blocked.',
        'docker compose exit 127; psql exit 127; sudo apt-get requested a password',
        'Used unpacked PostgreSQL 16.14 under /tmp with a local Unix socket; no system install or external listener.',
        :'run_id'
    ),
    (
        'SQL-001',
        'Data Model',
        'Low',
        'G2',
        'Resolved',
        'First reconciliation attempt could not load optional LLVM JIT library.',
        'The first reconciliation transaction rolled back before audit rows were inserted.',
        'PostgreSQL error loading llvmjit.so/libLLVM-17.so.1',
        'Set LOCAL jit=off in deterministic Wave 1 analytical SQL; calculations and thresholds were unchanged.',
        :'run_id'
    ),
    (
        'VAL-001',
        'Validation',
        'Medium',
        'G3',
        'Resolved',
        'Attempt 1 used inconsistent signal identifiers delinquent_months and delinquent_months_6m.',
        'Independent validation blocked Gate 3 and reporting.',
        'outputs/qa/wave1_independent_validation.json',
        'Aligned the canonical identifier to delinquent_months_6m and wrote a new, non-overwriting attempt 2 that passed.',
        :'run_id'
    ),
    (
        'DATA-001',
        'SQL QA',
        'Medium',
        'G2',
        'Open',
        'The source contains values outside UCI-documented education, marriage, and repayment code descriptions.',
        'Those fields require caution in categorical interpretation; no source row or value was changed.',
        'audit.test_result DQ-016, DQ-017, DQ-018',
        NULL,
        :'run_id'
    );
