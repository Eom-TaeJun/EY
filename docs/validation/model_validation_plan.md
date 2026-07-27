# Model Validation Plan

Status: Wave 2 model conclusions remain deferred. The Wave 1 independent
validation interface is implemented but cannot recommend release until a real
source-backed run is reproduced.

## Preconditions

- Gates 1–3 must have evidence from one non-blank run ID.
- Gate evidence must validate with `src/validation/gate_evidence.py`.
- The independent reproduction input is a deterministic snapshot, not a copied
  Gate packet. Its sections are `source`, `core`, `sql_tests`, and `signals`.
- Missing source, database, snapshot, result, or check evidence is `blocked` or
  `fail`; it is never converted to `pass`.
- Validation does not repair Builder SQL or relax values in
  `config/validation_thresholds.yml`.

## Wave 1 independent checks

The validation-owned Python path recomputes:

- source-to-raw row difference and unlogged rejects
- borrower-month expectation (`borrowers × 6`)
- bill and payment differences using the configured amount tolerance
- unique SQL-test count, failed tests, and required evidence fields
- signal definition, observation-timing, leakage, and SQL coverage
- signal-bucket and risk-band sample totals
- observed default rates from `default_count / sample_count`

Required snapshot fields are deliberately explicit:

| Section | Required evidence |
|---|---|
| `source` | source ID, registry path, SHA-256, source rows/columns, raw rows, registration flag, unlogged rejects |
| `core` | borrower and account-month rows, six-month factor, borrower and account-month key failures, orphan rows, required-history/code failures, wide/long bill and payment totals |
| `sql_tests[]` | unique test ID, status, tested/failed rows, severity, affected object; at least 12 unique passing tests |
| `signals.definitions[]` | versioned signal ID, rationale, observation timing, timing/leakage status, deterministic SQL artifact |
| `signals.outcomes[]` | signal bucket, sample count, default count; totals must tie to borrowers for every signal |
| `signals.risk_bands[]` | risk band, sample count, default count; bands must tie to borrowers |

The planned PostgreSQL handoff uses `audit.test_result`,
`audit.reconciliation_result`, `audit.issue_log`,
`mart.borrower_risk_signal`, `mart.signal_default_summary`, and
`mart.risk_band_summary`. Until a deterministic exporter supplies the snapshot
from those objects, database reproduction is blocked rather than passed.

The gate JSON schema version is `1.0` and requires:

- `gate`, `run_id`, timezone-aware `generated_at`, and `producer`
- overall `status`
- unique `checks[].check_id`
- an allowed check status and non-empty structured evidence for every check
- all required check IDs from Gates 1–5

Gate-specific numeric evidence is recomputed and challenged. Duplicate JSON
keys, `NaN`/infinite values, missing artifacts, duplicate check IDs, inconsistent
totals, incomplete summaries, and fewer than 12 SQL tests fail closed.

Reproduction command after the Builder creates a real snapshot:

```bash
python -m src.validation.wave1_reproduction \
  --snapshot outputs/qa/wave1_snapshot.json \
  --output outputs/qa/wave1_independent_validation.json
```

The command refuses to overwrite an existing result. Gate packets may be
emitted to a new run-specific directory with `--emit-gate-packets`; the
Orchestrator remains responsible for the canonical Gate checkpoint.

## Wave 2 required checks

- clear target and observation window
- no future information in features
- time-aware or explicitly justified pseudo-temporal split
- baseline versus behavioral feature comparison
- discrimination and calibration
- segment and stability review
- error-case analysis
- coefficient or feature-direction reasonableness
- threshold selection separated from final evaluation
- SQL/Python population and outcome reconciliation
- model run ID and definition-version consistency
- explicit `proxy`, `prototype`, or `simulation` labels for Stage, EAD, LGD, and
  ECL outputs not supported as actual IFRS 9 estimates

The Validation role must be independent from the model Builder role. A passing
machine contract is evidence for an approval decision, not the approval itself.
