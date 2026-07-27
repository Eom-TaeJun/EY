# Risk Component Agent Contract

## Objective

Implement explainable, time-aware PD and explicitly labelled proxy components
only where the available public data supports them.

## Outputs

- baseline and behavioral PD prototypes
- model run and definition versions
- Stage/EAD prototypes and sensitivity interfaces when supported
- calibration, stability, and SQL/Python reconciliation inputs

## Owned paths

- `sql/risk_components/`
- `src/models/`
- `config/scenarios.yml`
- `docs/methodology/risk_component_scope.md`

## Rules

- Gate 3 must pass before model conclusions
- label Stage, EAD, LGD, and ECL as proxy, prototype, or simulation
- do not claim unsupported LGD or EAD estimates
- do not approve or validate the component's own outputs
