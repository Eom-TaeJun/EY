$ErrorActionPreference = "Stop"

$dirs = @(
  "data/raw", "data/interim", "data/processed", "data/samples",
  "logs/ingestion", "logs/pipeline", "logs/validation",
  "outputs/qa", "outputs/model", "outputs/charts", "outputs/excel", "outputs/final",
  "sql/ddl", "sql/ingestion", "sql/staging", "sql/quality", "sql/business_rules",
  "sql/reconciliation", "sql/features", "sql/risk_components", "sql/reporting",
  "src/ingestion", "src/transformation", "src/features", "src/models",
  "src/validation", "src/reporting", "src/common",
  "tests/unit", "tests/integration", "tests/data_quality", "tests/regression",
  "presentation"
)

foreach ($dir in $dirs) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  New-Item -ItemType File -Force -Path (Join-Path $dir ".gitkeep") | Out-Null
}

python scripts/validate_scaffold.py
