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
	python scripts/check_gate.py --gate 1

gate2:
	python scripts/check_gate.py --gate 2

gate3:
	python scripts/check_gate.py --gate 3

gate4:
	python scripts/check_gate.py --gate 4

gate5:
	python scripts/check_gate.py --gate 5

test:
	pytest -q
