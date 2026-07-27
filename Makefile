.PHONY: help db-up db-down scaffold-check gate0 gate1 gate2 gate3 gate4 gate5 test

help:
	@echo "db-up          Start PostgreSQL"
	@echo "db-down        Stop PostgreSQL"
	@echo "scaffold-check Validate required repository files"
	@echo "gate0          Validate Wave 0 governance readiness"
	@echo "gate1..gate5   Validate deterministic evidence for the selected gate"
	@echo "test           Run available tests"

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

scaffold-check:
	python scripts/validate_scaffold.py

gate0:
	python scripts/validate_scaffold.py
	python scripts/validate_governance.py

gate1:
	python -m scripts.check_gate --gate 1 --packet-directory outputs/qa/validated/latest

gate2:
	python -m scripts.check_gate --gate 2 --packet-directory outputs/qa/validated/latest

gate3:
	python -m scripts.check_gate --gate 3 --packet-directory outputs/qa/validated/latest

gate4:
	python -m scripts.check_gate --gate 4 --packet-directory outputs/qa/validated/latest

gate5:
	python -m scripts.check_gate --gate 5 --packet-directory outputs/qa/validated/latest

test:
	python -m pytest -q
