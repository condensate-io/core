# Condensates — Docker-first test targets (run from WSL)
#
#   make test              # unit + SDK suites (no GPU stack required)
#   make test-integration    # Postgres + Qdrant integration tests
#   make test-all            # everything above + benchmark demo

COMPOSE := docker compose -f docker-compose.yml -f docker-compose.test.yml
COMPOSE_TEST := $(COMPOSE) --profile test

PYTEST_UNIT := tests/ --ignore=tests/test_schema_integrity.py --ignore=tests/test_omnisim_scenarios.py -m "not integration"

.PHONY: test test-python test-ts test-go test-mcp test-benchmarks test-contradiction test-integration test-all
.PHONY: lint-ci lint-python lint-frontend npm-install-frontend npm-install-mcp

test: test-python test-ts test-go test-mcp

test-python:
	$(COMPOSE_TEST) run --rm --no-deps test-python $(PYTEST_UNIT) benchmarks/tests/ -q

test-ts:
	$(COMPOSE_TEST) run --rm test-ts-sdk

test-go:
	$(COMPOSE_TEST) run --rm test-go-sdk

test-mcp:
	$(COMPOSE_TEST) run --rm test-mcp-bridge

test-benchmarks:
	$(COMPOSE_TEST) run --rm --no-deps test-benchmarks \
		--backend full_context --output /tmp/bench-demo.json

test-contradiction:
	$(COMPOSE_TEST) run --rm --no-deps test-contradiction \
		--backend both --output /tmp/contradiction-report.json

test-integration:
	$(COMPOSE) up -d condensate-db condensate-vector
	$(COMPOSE_TEST) run --rm test-python sh -c "alembic upgrade head && pytest tests/test_integration_stack.py -v -m integration"

test-all: test test-integration test-benchmarks test-contradiction

# CI parity — run from WSL only (never host pip/npm)
lint-ci: lint-python lint-frontend

lint-python:
	$(COMPOSE_TEST) run --rm --no-deps lint-python

lint-frontend:
	$(COMPOSE_TEST) run --rm lint-frontend

npm-install-frontend:
	$(COMPOSE_TEST) run --rm npm-install-frontend

npm-install-mcp:
	$(COMPOSE_TEST) run --rm npm-install-mcp
