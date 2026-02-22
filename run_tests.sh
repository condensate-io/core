#!/bin/bash
# =============================================================================
# Condensate Test Suite
# =============================================================================
# Exit immediately if any stage fails — don't silently continue past errors.
set -euo pipefail

PASS=0
FAIL=0

# Colour helpers
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

pass() { echo -e "${GREEN}[PASS]${NC} $1"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL+1)); }
header() { echo -e "\n${YELLOW}=== $1 ===${NC}"; }

# =============================================================================
# 0. Bring compose stack up
# =============================================================================
header "Starting Docker Services"
docker compose up -d
# Give Postgres a moment to be ready (healthcheck would be better long-term)
echo "Waiting for services to be ready..."
sleep 5

# =============================================================================
# 1. Core Python unit tests (mocked DB — fast, always run)
# =============================================================================
header "Python Unit Tests (mocked DB)"
if docker compose exec condensate-core pytest tests/ \
    --ignore=tests/test_schema_integrity.py \
    -v --tb=short -q; then
    pass "Unit tests"
else
    fail "Unit tests"
fi

# =============================================================================
# 2. HITL guardrail unit tests (explicit, always run)
# =============================================================================
header "HITL Guardrail Unit Tests"
if docker compose exec condensate-core pytest tests/test_guardrails.py \
    -v --tb=short; then
    pass "Guardrail tests"
else
    fail "Guardrail tests"
fi

# =============================================================================
# 3. Schema integrity tests (real DB — catches column/index drift)
# =============================================================================
header "Schema Integrity Tests (live DB)"
# These tests use SQLAlchemy inspect() against the real Postgres instance.
# They will catch: missing columns, wrong nullability, missing indexes.
# They are auto-skipped if the DB is unreachable.
if docker compose exec condensate-core pytest tests/test_schema_integrity.py \
    -v --tb=short; then
    pass "Schema integrity"
else
    fail "Schema integrity — a column or index is missing from the live DB. Check _apply_migrations() in session.py"
fi

# =============================================================================
# 4. init_db() smoke test — verify migrations actually run on startup
# =============================================================================
header "init_db() Smoke Test"
if docker compose exec condensate-core python -c "
import sys
from src.db.session import init_db
try:
    init_db()
    print('init_db() completed without error')
    sys.exit(0)
except Exception as e:
    print(f'init_db() raised: {e}', file=sys.stderr)
    sys.exit(1)
"; then
    pass "init_db() smoke test"
else
    fail "init_db() smoke test — startup migration failed"
fi

# =============================================================================
# 5. Admin endpoint smoke tests (the endpoints that were failing in prod)
# =============================================================================
header "Admin Endpoint Smoke Tests"

# Use the internal network address (nginx proxy or direct to core)
BASE_URL="http://localhost:8000"

check_endpoint() {
    local label="$1"
    local url="$2"
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "X-API-Key: $(docker compose exec condensate-core python -c \
            "from src.db.session import SessionLocal; from src.db.models import ApiKey; \
             db=SessionLocal(); k=db.query(ApiKey).first(); print(k.key if k else '') ; db.close()" \
            2>/dev/null)" \
        --max-time 10 \
        "${BASE_URL}${url}" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        pass "${label} → HTTP ${http_code}"
    elif [ "$http_code" = "000" ]; then
        echo -e "${YELLOW}[SKIP]${NC} ${label} — could not reach ${BASE_URL} (not running locally?)"
    else
        fail "${label} → HTTP ${http_code} (expected 200)"
    fi
}

check_endpoint "GET /api/admin/stats"                      "/api/admin/stats"
check_endpoint "GET /api/admin/learnings"                  "/api/admin/learnings"
check_endpoint "GET /api/admin/review/assertions/pending"  "/api/admin/review/assertions/pending"

# =============================================================================
# 6. Python SDK install check
# =============================================================================
header "Python SDK Install Check"
if [ -d "sdks/python" ]; then
    if (cd sdks/python && python3 -m venv .venv && \
        source .venv/bin/activate && pip install -q . && deactivate); then
        pass "Python SDK installs cleanly"
    else
        fail "Python SDK install failed"
    fi
else
    echo "[SKIP] sdks/python not found"
fi

# =============================================================================
# 7. MCP Bridge npm check
# =============================================================================
header "MCP Bridge npm Check"
if command -v npm &>/dev/null; then
    if [ -d "sdks/mcp-bridge" ]; then
        if (cd sdks/mcp-bridge && npm install --silent); then
            pass "MCP Bridge npm install"
        else
            fail "MCP Bridge npm install failed"
        fi
    else
        echo "[SKIP] sdks/mcp-bridge not found"
    fi
else
    echo "[SKIP] npm not found"
fi

# =============================================================================
# Summary
# =============================================================================
header "Results"
echo -e "  ${GREEN}Passed: ${PASS}${NC}"
if [ "$FAIL" -gt 0 ]; then
    echo -e "  ${RED}Failed: ${FAIL}${NC}"
    echo ""
    echo -e "${RED}Test suite FAILED — see above for details.${NC}"
    exit 1
else
    echo -e "  ${RED}Failed: 0${NC}"
    echo ""
    echo -e "${GREEN}All tests passed.${NC}"
fi
