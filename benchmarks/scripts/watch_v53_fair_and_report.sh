#!/usr/bin/env bash
# Poll until v5.3 fair LoCoMo run completes (10 conversations), then merge reports and update docs.
set -eu
cd "$(dirname "$0")/../.."
LOG="benchmarks/results/locomo10_v53_fair.log"
JSON="benchmarks/results/locomo10_condensate_v53_fair.json"
POLL_SEC="${LOCOMO_WATCH_POLL_SEC:-300}"
EXPECTED=10

log() { echo "[watch-v53] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

count_samples() {
  python3 -c "
import json, sys
path = sys.argv[1]
try:
    data = json.loads(open(path, encoding='utf-8').read())
    reports = data.get('backends', {}).get('condensate', {}).get('sample_reports', [])
    print(len(reports))
except Exception:
    print(0)
" "$JSON"
}

wait_for_complete() {
  log "Watching $JSON (poll every ${POLL_SEC}s, expect ${EXPECTED} conversations)"
  while true; do
    n="$(count_samples)"
    if [ "$n" -ge "$EXPECTED" ]; then
      if grep -q "Checkpoint: condensate complete" "$LOG" 2>/dev/null; then
        log "Complete: ${n}/${EXPECTED} sample_reports + checkpoint in log"
        return 0
      fi
      log "JSON has ${n} samples; waiting for final checkpoint in log..."
    else
      tail_line=""
      if [ -f "$LOG" ]; then
        tail_line="$(tail -1 "$LOG" 2>/dev/null || true)"
      fi
      log "Progress: ${n}/${EXPECTED} sample_reports — ${tail_line}"
    fi
    sleep "$POLL_SEC"
  done
}

run_report_pipeline() {
  log "Running make test-locomo-report"
  make test-locomo-report
  log "Updating COMPETITIVE_POSITIONING.md"
  python3 benchmarks/scripts/update_positioning_v53_fair.py \
    --input "$JSON" \
    --positioning benchmarks/docs/COMPETITIVE_POSITIONING.md
  log "Done. Artifacts: locomo10_full_report.json, locomo10_comparative_report.md"
}

wait_for_complete
run_report_pipeline
