.PHONY: help db-up db-down scaffold-check test

help:
	@echo "db-up          Start PostgreSQL"
	@echo "db-down        Stop PostgreSQL"
	@echo "scaffold-check Validate required repository files"
	@echo "test           Run available tests"

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

scaffold-check:
	python scripts/validate_scaffold.py

test:
	pytest -q
