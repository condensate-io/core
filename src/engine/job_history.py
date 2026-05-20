from datetime import datetime
from collections import deque
import threading
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Job History Log (ring buffer – last 200 runs, thread-safe)
# ---------------------------------------------------------------------------
_JOB_LOG: deque[Dict[str, Any]] = deque(maxlen=200)
_JOB_LOG_LOCK = threading.Lock()


def log_job(job_id: str, job_name: str, status: str,
            started_at: datetime, finished_at: datetime | None = None,
            duration_ms: int | None = None, error: str | None = None) -> None:
    entry = {
        "job_id": job_id,
        "job_name": job_name,
        "status": status,          # "running" | "success" | "error"
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat() if finished_at else None,
        "duration_ms": duration_ms,
        "error": error,
    }
    with _JOB_LOG_LOCK:
        # Replace an existing "running" entry for the same job if present
        for e in _JOB_LOG:
            if e["job_id"] == job_id and e.get("status") == "running":
                e.update(entry)
                return
        _JOB_LOG.appendleft(entry)


def get_job_log() -> List[Dict[str, Any]]:
    """Return a snapshot of the job log (newest first)."""
    with _JOB_LOG_LOCK:
        return list(_JOB_LOG)
