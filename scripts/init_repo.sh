#!/usr/bin/env bash
set -euo pipefail

mkdir -p \
  data/{raw,interim,processed,samples} \
  logs/{ingestion,pipeline,validation} \
  outputs/{qa,model,charts,excel,final} \
  sql/{ddl,ingestion,staging,quality,business_rules,reconciliation,features,risk_components,reporting} \
  src/{ingestion,transformation,features,models,validation,reporting,common} \
  tests/{unit,integration,data_quality,regression} \
  presentation

for dir in data/raw data/interim data/processed data/samples logs/ingestion logs/pipeline logs/validation outputs/qa outputs/model outputs/charts outputs/excel outputs/final sql/ddl sql/ingestion sql/staging sql/quality sql/business_rules sql/reconciliation sql/features sql/risk_components sql/reporting src/ingestion src/transformation src/features src/models src/validation src/reporting src/common tests/unit tests/integration tests/data_quality tests/regression presentation; do
  touch "$dir/.gitkeep"
done

python scripts/validate_scaffold.py
