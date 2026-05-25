"""HTTP adapter for Condensate API — handles ingestion and retrieval."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from benchmarks.metrics.tokens import count_tokens


class CondensateBackend:
    """Calls /api/v1/episodic and /api/v1/memory/retrieve on a live Condensate stack."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        project_id: str = "00000000-0000-0000-0000-000000000000",
        condensation_timeout_s: float = 120.0,
        poll_interval_s: float = 2.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("CONDENSATE_URL", "http://condensate-core:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("CONDENSATE_API_KEY")
        self.project_id = project_id
        self.condensation_timeout_s = condensation_timeout_s
        self.poll_interval_s = poll_interval_s
        self._session_projects: dict[str, str] = {}
        self._client = httpx.Client(timeout=60.0)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def reset(self, session_id: str) -> None:
        self._session_projects[session_id] = self.project_id

    def add(self, session_id: str, messages: list[dict]) -> None:
        project_id = self._session_projects.get(session_id, self.project_id)
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            payload: dict[str, Any] = {
                "project_id": project_id,
                "source": "benchmark",
                "text": f"{role}: {content}",
                "metadata": {"session_id": session_id, "role": role},
            }
            response = self._client.post(
                f"{self.base_url}/api/v1/episodic",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
        self.wait_for_condensation(session_id)

    def wait_for_condensation(self, session_id: str) -> None:
        """Poll retrieve until a response is returned or timeout elapses."""
        deadline = time.monotonic() + self.condensation_timeout_s
        probe_query = f"session {session_id} context"
        while time.monotonic() < deadline:
            try:
                response = self._client.post(
                    f"{self.base_url}/api/v1/memory/retrieve",
                    json={"query": probe_query},
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(self.poll_interval_s)

    def search(self, session_id: str, query: str) -> str:
        response = self._client.post(
            f"{self.base_url}/api/v1/memory/retrieve",
            json={"query": query},
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        answer = data.get("answer") or data.get("context") or ""
        if isinstance(answer, list):
            return "\n".join(str(x) for x in answer)
        return str(answer)

    def token_count(self, text: str) -> int:
        return count_tokens(text)

    def close(self) -> None:
        self._client.close()
