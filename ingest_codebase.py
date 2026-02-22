"""
Ingest the Condensates codebase into memory via the MCP store_memory API.
Usage: python ingest_codebase.py
"""
import os
import requests
import time

API_URL = "http://localhost:8000/mcp/tools/call"
API_KEY = "sk-5b074364-a89a-486c-94ff-79ad7daf6326"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# File extensions to include
INCLUDE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".yml", ".yaml",
    ".json", ".sh", ".txt", ".html", ".css", ".toml", ".cfg", ".ini",
    ".sql", ".env.example"
}

# Directories to skip entirely
SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", "node_modules",
    "dist", ".venv", "venv", "env", ".mypy_cache", "sdks",
    "scratch", "project_website"
}

# Max file size to ingest (bytes) - skip very large files
MAX_FILE_SIZE = 64 * 1024  # 64KB

ROOT = os.path.dirname(os.path.abspath(__file__))

def should_include(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() in INCLUDE_EXTS

def collect_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if should_include(fpath):
                size = os.path.getsize(fpath)
                if size <= MAX_FILE_SIZE and size > 0:
                    files.append(fpath)
    return files

TIMEOUT = 120          # seconds — generous enough for NER model cold-start
MAX_RETRIES = 3        # retry on timeout/connection errors

def ingest_file(fpath: str) -> bool:
    rel_path = os.path.relpath(fpath, ROOT)
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip()
        if not content:
            return False

        # Format as a meaningful memory chunk
        text = f"FILE: {rel_path}\n\n{content}"

        payload = {
            "name": "store_memory",
            "arguments": {
                "content": text,
                "type": "episodic",
                "metadata": {
                    "file_path": rel_path,
                    "source": "codebase_ingest"
                }
            }
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=TIMEOUT)
                if resp.status_code == 200:
                    return True
                else:
                    print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
                    return False  # Non-transient error, don't retry
            except requests.exceptions.Timeout:
                wait = attempt * 5
                print(f"  TIMEOUT (attempt {attempt}/{MAX_RETRIES}), retrying in {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            except requests.exceptions.ConnectionError as e:
                print(f"  CONNECTION ERROR: {e}")
                return False

        print(f"  GAVE UP after {MAX_RETRIES} attempts")
        return False
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        return False


def main():
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    workers = int(os.getenv("INGEST_WORKERS", "8"))

    print(f"Collecting files from: {ROOT}")
    files = collect_files()
    total = len(files)
    print(f"Found {total} files to ingest. Running with {workers} parallel workers.\n")

    ok = 0
    fail = 0
    done = 0
    lock = threading.Lock()

    def _ingest(fpath: str):
        rel = os.path.relpath(fpath, ROOT)
        success = ingest_file(fpath)
        return rel, success

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_ingest, f): f for f in files}
        for future in as_completed(futures):
            rel, success = future.result()
            with lock:
                done += 1
                if success:
                    ok += 1
                    status = "OK"
                else:
                    fail += 1
                    status = "FAIL"
                print(f"[{done}/{total}] {rel} ... {status}", flush=True)

    print(f"\n{'='*50}")
    print(f"Done. Ingested: {ok} | Failed: {fail} | Total: {total}")

if __name__ == "__main__":
    main()
