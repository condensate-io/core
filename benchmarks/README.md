# Condensate benchmark harness

Run memory-system benchmarks (LoCoMo, LongMemEval) against Condensate or baselines.

## Layout

```text
benchmarks/
  backends/       MemoryBackend implementations
  metrics/        Token counting (tiktoken)
  runners/          CLI entrypoints
  results/          Output JSON (gitignored locally)
```

## Docker (required)

All commands run inside containers via WSL:

```bash
# Demo cycle with full-context baseline (no live stack required)
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && make test-benchmarks"

# Against live Condensate API (start db + core first)
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose up -d condensate-db condensate-vector condensate-core"
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm test-benchmarks --backend condensate --output /tmp/bench-condensate.json"
```

## ContradictionBench

```bash
wsl -e bash -lc "cd /mnt/c/LocalProjects/Condensates && make test-contradiction"
```

50 synthetic supersession cases in `benchmarks/data/contradiction_cases.json` (generated on first run). Compares `full_context` (should fail) vs `structured` (active-only, should pass).

## Environment

| Variable | Description |
| -------- | ----------- |
| `CONDENSATE_URL` | API base URL (default `http://condensate-core:8000`) |
| `CONDENSATE_API_KEY` | Bearer token when auth is enabled |

## Next steps (roadmap)

- Wire LoCoMo dataset from `mem0ai/memory-benchmarks`
- Add judge + scoring in `metrics/judge.py`
- Publish weekly regression via CI (optional)
