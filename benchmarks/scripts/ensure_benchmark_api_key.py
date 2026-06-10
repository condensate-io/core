#!/usr/bin/env python3
"""Ensure a valid CONDENSATE_API_KEY exists for LoCoMo fair runs.

Bulk ingest (/api/v1/episodic/bulk) is unauthenticated; retrieve requires a key.
Without this, ingest completes then every QA retrieve fails with 401.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

import httpx

DEFAULT_BASE = "http://condensate-core:8000"
BENCH_PROJECT = "locomo-benchmark"
KEY_NAME = "locomo-benchmark"


def _base_url() -> str:
    return os.getenv("CONDENSATE_URL", DEFAULT_BASE).rstrip("/")


def _wait_for_core(
    client: httpx.Client,
    base_url: str,
    timeout_s: float = 180.0,
    interval_s: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{base_url}/healthz")
            if response.status_code < 500:
                return
            last_error = f"healthz status {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(interval_s)
    raise RuntimeError(
        f"condensate-core not ready at {base_url} after {timeout_s:.0f}s ({last_error})"
    )


def _probe_key(client: httpx.Client, base_url: str, api_key: str) -> bool:
    project_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, BENCH_PROJECT))
    try:
        response = client.post(
            f"{base_url}/api/v1/memory/retrieve",
            json={"query": "benchmark key probe", "project_id": project_id, "session_id": "probe"},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        return response.status_code != 401
    except httpx.HTTPError:
        return False


def ensure_key(base_url: str | None = None) -> str:
    base = (base_url or _base_url()).rstrip("/")
    existing = os.getenv("CONDENSATE_API_KEY", "").strip()
    placeholder_markers = ("your-api-key", "changeme", "sk-your", "example")
    if existing and any(m in existing.lower() for m in placeholder_markers):
        existing = ""

    with httpx.Client(timeout=60.0) as client:
        _wait_for_core(client, base)
        if existing and _probe_key(client, base, existing):
            return existing

        response = client.post(
            f"{base}/api/admin/keys",
            params={"name": KEY_NAME, "project_id": BENCH_PROJECT},
        )
        response.raise_for_status()
        key = str(response.json()["key"]).strip()
        if not key:
            raise RuntimeError("admin /keys returned empty key")
        if not _probe_key(client, base, key):
            raise RuntimeError("newly created API key failed retrieve probe (401)")
        return key


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure benchmark API key")
    parser.add_argument("--base-url", default=None, help="Condensate API base URL")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Print shell export: CONDENSATE_API_KEY=...",
    )
    args = parser.parse_args()
    try:
        key = ensure_key(args.base_url)
    except httpx.HTTPError as exc:
        print(f"ensure_benchmark_api_key failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.export:
        print(f"export CONDENSATE_API_KEY={key}")
    else:
        sys.stdout.write(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
