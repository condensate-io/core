#!/usr/bin/env bash
# Preflight for the LoCoMo fair harness.
#
# The fair benchmark MUST run against a condensate-core that has
# RETRIEVE_BENCHMARK_MODE=1 (plus the deterministic retrieval knobs from
# benchmarks/docker-compose.bench.yml). If the API container is started
# without that overlay, benchmark_mode is False at request time: the recall
# gate runs LLM refinement, the evidence verifier strips/abstains, and the
# multi-query expansion is disabled. That silently halves retrieved context
# and tanks accuracy (observed: 85% -> ~67%). This guard fails loudly instead.
set -euo pipefail

required_true="RETRIEVE_BENCHMARK_MODE"
# Knobs that define the fair-run retrieval contract; warn if missing.
expected_vars=(
  "RETRIEVE_BENCHMARK_MODE"
  "RETRIEVE_SKIP_RERANK"
  "RETRIEVE_VECTOR_LIMIT"
  "RETRIEVE_RERANK_TOP_N"
  "RETRIEVE_ASSERTION_LIMIT"
)

cid="$(docker ps --filter name=condensate-core -q | head -1)"
if [ -z "$cid" ]; then
  echo "PREFLIGHT FAIL: condensate-core container is not running." >&2
  exit 1
fi

env_dump="$(docker exec "$cid" printenv)"

bench_val="$(printf '%s\n' "$env_dump" | grep -E "^${required_true}=" | head -1 | cut -d= -f2- || true)"
case "${bench_val,,}" in
  1|true|yes)
    : ;;
  *)
    echo "PREFLIGHT FAIL: ${required_true} is not enabled on condensate-core (value='${bench_val}')." >&2
    echo "  The API must be (re)created with the bench overlay so benchmark_mode is live:" >&2
    echo "    docker compose -f docker-compose.yml -f benchmarks/docker-compose.bench.yml up -d --force-recreate --no-deps condensate-core" >&2
    exit 1 ;;
esac

missing=()
for v in "${expected_vars[@]}"; do
  if ! printf '%s\n' "$env_dump" | grep -qE "^${v}="; then
    missing+=("$v")
  fi
done

echo "PREFLIGHT OK: benchmark_mode is live on condensate-core ($cid)."
printf '%s\n' "$env_dump" | grep -E '^RETRIEVE_' | sort | sed 's/^/  /'
if [ "${#missing[@]}" -gt 0 ]; then
  echo "PREFLIGHT WARN: missing expected fair-run vars: ${missing[*]}" >&2
fi
