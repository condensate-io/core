# Condensates — Docker-first test targets (run from WSL)
#
#   make test              # unit + SDK suites (no GPU stack required)
#   make test-integration    # Postgres + Qdrant integration tests
#   make test-all            # everything above + benchmark demo

COMPOSE := docker compose -f docker-compose.yml -f docker-compose.test.yml
COMPOSE_TEST := $(COMPOSE) --profile test

PYTEST_UNIT := tests/ --ignore=tests/test_schema_integrity.py --ignore=tests/test_omnisim_scenarios.py -m "not integration"

.PHONY: test test-python test-ts test-go test-mcp test-benchmarks test-locomo-full test-locomo-v53-fair test-locomo-v53-fair-resume test-locomo-watch test-locomo-report test-contradiction test-integration test-all
.PHONY: lint-ci lint-python lint-frontend npm-install-frontend npm-install-mcp npm-audit

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
		--backend all --skip-condensate --output /tmp/bench-locomo.json

test-locomo-full:
	$(COMPOSE) -f benchmarks/docker-compose.bench.yml up -d condensate-db condensate-vector condensate-ollama condensate-core
	$(COMPOSE_TEST) -f benchmarks/docker-compose.bench.yml run --rm test-benchmarks \
		--dataset /app/benchmarks/data/locomo10.json \
		--backend condensate \
		--resume \
		--output /app/benchmarks/results/locomo10_full_report.json
	$(MAKE) test-locomo-report

# P0: fair v5.3 full run — fresh ingest per conversation (never CONDENSATE_SKIP_INGEST=1)
test-locomo-v53-fair:
	$(COMPOSE) -f docker-compose.yml -f benchmarks/docker-compose.bench.yml up -d condensate-db condensate-vector condensate-ollama condensate-core
	CONDENSATE_SKIP_INGEST=0 $(COMPOSE) -f docker-compose.yml -f docker-compose.test.yml -f benchmarks/docker-compose.bench.yml run --rm test-benchmarks \
		--dataset /app/benchmarks/data/locomo10.json \
		--backend condensate \
		--output /app/benchmarks/results/locomo10_condensate_v53_fair.json \
		2>&1 | tee benchmarks/results/locomo10_v53_fair.log

test-locomo-v53-fair-resume:
	$(COMPOSE) -f docker-compose.yml -f benchmarks/docker-compose.bench.yml up -d condensate-db condensate-vector condensate-ollama condensate-core
	CONDENSATE_SKIP_INGEST=0 $(COMPOSE) -f docker-compose.yml -f docker-compose.test.yml -f benchmarks/docker-compose.bench.yml run --rm test-benchmarks \
		--dataset /app/benchmarks/data/locomo10.json \
		--backend condensate \
		--resume \
		--output /app/benchmarks/results/locomo10_condensate_v53_fair.json \
		2>&1 | tee -a benchmarks/results/locomo10_v53_fair.log

test-locomo-watch:
	wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && chmod +x benchmarks/scripts/watch_v53_fair_and_report.sh && nohup benchmarks/scripts/watch_v53_fair_and_report.sh >> benchmarks/results/locomo10_v53_watch.log 2>&1 &"
	@echo "Watch started — tail benchmarks/results/locomo10_v53_watch.log"

test-locomo-report:
	$(COMPOSE_TEST) run --rm --no-deps --entrypoint python test-benchmarks \
		benchmarks/scripts/merge_locomo_reports.py \
		--base /app/benchmarks/results/locomo10_full_report.json \
		--sidecar /app/benchmarks/results/locomo10_condensate_v53_fair.json \
		--output /app/benchmarks/results/locomo10_full_report.json
	$(COMPOSE_TEST) run --rm --no-deps --entrypoint python test-benchmarks \
		benchmarks/runners/generate_comparative_report.py \
		--input /app/benchmarks/results/locomo10_full_report.json \
		--output /app/benchmarks/results/locomo10_comparative_report.md
	$(COMPOSE_TEST) run --rm --no-deps --entrypoint python test-benchmarks \
		benchmarks/runners/generate_comparative_report_user_html.py \
		--input /app/benchmarks/results/locomo10_full_report.json \
		--output /app/benchmarks/results/locomo10_comparative_report.html
	$(COMPOSE_TEST) run --rm --no-deps --entrypoint python test-benchmarks \
		benchmarks/scripts/analyze_locomo_report.py \
		--input /app/benchmarks/results/locomo10_full_report.json

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

npm-audit: npm-audit-frontend npm-audit-mcp

npm-audit-frontend:
	$(COMPOSE_TEST) run --rm npm-audit-frontend

npm-audit-mcp:
	$(COMPOSE_TEST) run --rm npm-audit-mcp
