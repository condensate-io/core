"""HTTP adapter for Condensate API — bulk ingest and session-scoped retrieval."""

from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any

import httpx

from benchmarks.data.locomo_loader import (
    conversation_messages_for_ingest,
    observation_messages,
    session_summary_messages,
)
from benchmarks.metrics.tokens import count_tokens


def _project_id(session_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))


class CondensateBackend:
    """Calls /api/v1/episodic/bulk and /api/v1/memory/retrieve on a live Condensate stack."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        condensation_timeout_s: float = 120.0,
        poll_interval_s: float = 2.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("CONDENSATE_URL", "http://condensate-core:8000")).rstrip(
            "/"
        )
        raw_key = api_key if api_key is not None else os.getenv("CONDENSATE_API_KEY", "")
        self.api_key = raw_key.strip() or None
        self.condensation_timeout_s = condensation_timeout_s
        self.poll_interval_s = poll_interval_s
        self.bulk_chunk_size = int(os.getenv("LOCOMO_BULK_CHUNK_SIZE", "15"))
        self.bulk_retries = int(os.getenv("CONDENSATE_BULK_RETRIES", "6"))
        self.retrieve_retries = int(os.getenv("CONDENSATE_RETRIEVE_RETRIES", "24"))
        self.qa_delay_s = float(os.getenv("CONDENSATE_QA_DELAY_S", "0"))
        self.last_strategy = ""
        self.last_native_answer = ""
        read_timeout = float(os.getenv("CONDENSATE_HTTP_READ_TIMEOUT", "900"))
        self._client = httpx.Client(timeout=httpx.Timeout(60.0, read=read_timeout))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def reset(self, session_id: str) -> None:
        del session_id

    def add(self, session_id: str, messages: list[dict]) -> None:
        """Single-message ingest path (mini tests). Prefer ingest_sample for LoCoMo."""
        project_id = _project_id(session_id)
        episodes = [self._message_to_episode(project_id, session_id, msg) for msg in messages]
        if episodes:
            self._bulk_post_with_retry(project_id, episodes)

    def ingest_sample(self, session_id: str, sample: dict[str, Any]) -> None:
        """Full LoCoMo ingest: dialog + observations + session summaries."""
        project_id = _project_id(session_id)
        episodes: list[dict[str, Any]] = []
        for msg in conversation_messages_for_ingest(sample["conversation"]):
            episodes.append(self._message_to_episode(project_id, session_id, msg))
        for msg in observation_messages(sample):
            episodes.append(self._message_to_episode(project_id, session_id, msg))
        for msg in session_summary_messages(sample):
            episodes.append(self._message_to_episode(project_id, session_id, msg))

        total_chunks = (len(episodes) + self.bulk_chunk_size - 1) // self.bulk_chunk_size
        for i in range(0, len(episodes), self.bulk_chunk_size):
            chunk_num = i // self.bulk_chunk_size + 1
            chunk = episodes[i : i + self.bulk_chunk_size]
            print(
                f"[condensate] {session_id} bulk chunk {chunk_num}/{total_chunks} "
                f"({len(chunk)} episodes, wait=True)...",
                file=sys.stderr,
                flush=True,
            )
            self._bulk_post_with_retry(project_id, chunk)
        print(
            f"[condensate] {session_id} ingest complete ({len(episodes)} episodes)",
            file=sys.stderr,
            flush=True,
        )

    def _message_to_episode(
        self, project_id: str, session_id: str, msg: dict[str, Any]
    ) -> dict[str, Any]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        meta = dict(msg.get("metadata") or {})
        meta.setdefault("session_id", session_id)
        meta.setdefault("role", role)
        text = content if role == "system" else f"{role}: {content}"
        return {
            "project_id": project_id,
            "source": "benchmark",
            "text": text,
            "metadata": meta,
        }

    def _bulk_post_with_retry(self, project_id: str, episodes: list[dict[str, Any]]) -> None:
        payload = {"project_id": project_id, "episodes": episodes, "wait": True}
        last_error: Exception | None = None
        for attempt in range(self.bulk_retries):
            try:
                response = self._client.post(
                    f"{self.base_url}/api/v1/episodic/bulk",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                last_error = exc
                time.sleep(min(2**attempt, 30))
        if last_error:
            raise last_error

    def wait_for_condensation(self, session_id: str) -> None:
        deadline = time.monotonic() + self.condensation_timeout_s
        probe_query = f"session {session_id} context"
        while time.monotonic() < deadline:
            try:
                ctx = self.search(session_id, probe_query)
                if ctx.strip():
                    return
            except httpx.HTTPError:
                pass
            time.sleep(self.poll_interval_s)

    def search(self, session_id: str, query: str) -> str:
        project_id = _project_id(session_id)
        payload = {"query": query, "project_id": project_id, "session_id": session_id}
        last_error: Exception | None = None
        for attempt in range(self.retrieve_retries):
            try:
                response = self._client.post(
                    f"{self.base_url}/api/v1/memory/retrieve",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
                context = str(data.get("context") or "")
                answer = str(data.get("answer") or "")
                self.last_strategy = str(data.get("strategy") or "")
                self.last_native_answer = answer if answer else context
                if self.qa_delay_s > 0:
                    time.sleep(self.qa_delay_s)
                return context if context else answer
            except httpx.HTTPError as exc:
                last_error = exc
                time.sleep(min(2**attempt, 30))
        if last_error:
            raise last_error
        return ""

    def token_count(self, text: str) -> int:
        return count_tokens(text)
