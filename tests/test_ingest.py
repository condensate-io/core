import time
import uuid
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.db.models import IngestJob
from src.ingest.service import IngestService


@pytest.fixture
def mock_db():
    return MagicMock()

def test_create_job(mock_db):
    service = IngestService(mock_db)
    job = service.create_job(
        project_id=uuid.uuid4(),
        source_type="web",
        source_config={"urls": ["http://example.com"]},
        trigger_type="on_demand",
        trigger_config={}
    )
    assert job.source_type == "web"
    mock_db.add.assert_called()

def test_run_job_success(mock_db):
    service = IngestService(mock_db)

    # Mock existing job
    job = IngestJob(
        id=uuid.uuid4(),
        source_type="web",
        source_config={"urls": ["http://example.com"]},
        state="active"
    )
    # Configure mock query to return job
    mock_db.query.return_value.filter.return_value.first.return_value = job
    # No previously-fetched artifacts for dedup lookup
    mock_db.execute.return_value.all.return_value = []

    # Mock Connector
    with patch("src.ingest.service.CONNECTORS") as mock_connectors:
        mock_conn = MagicMock()
        mock_connectors.get.return_value = mock_conn

        # Mock Discovery
        mock_conn.discover.return_value = [{"url": "http://example.com"}]

        # Mock Fetch
        mock_conn.fetch.return_value = [
            ("http://example.com", b"Hello World", {"status": 200})
        ]

        with patch.object(service, "_run_condensation_task") as mock_condense:
            run = service.run_job(job.id)

            # Condensation is dispatched on the shared background thread
            # pool; poll briefly for the fire-and-forget submit to land.
            deadline = time.monotonic() + 2.0
            while not mock_condense.called and time.monotonic() < deadline:
                time.sleep(0.01)
            mock_condense.assert_called_once()

        assert run.status == "completed"
        assert run.stats["fetch_failures"] == 0
        # 1 run + 1 artifact added
        assert mock_db.add.call_count >= 2


def test_load_existing_hashes_uses_latest_per_uri_query(mock_db):
    service = IngestService(mock_db)
    mock_db.execute.return_value.all.return_value = []

    service._load_existing_hashes(uuid.uuid4())

    stmt = mock_db.execute.call_args[0][0]
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "row_number() OVER" in compiled
    assert "PARTITION BY fetched_artifacts.source_uri" in compiled


class _ImmediateShard:
    current_workers = 4

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


def test_run_job_marks_partial_failure(mock_db):
    service = IngestService(mock_db)
    job = IngestJob(
        id=uuid.uuid4(),
        source_type="web",
        source_config={"urls": ["http://ok", "http://bad"]},
        state="active",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = job
    mock_db.execute.return_value.all.return_value = []

    def fetch(_config, item_ref):
        url = item_ref["url"]
        if url.endswith("bad"):
            raise RuntimeError("boom")
        return [(url, b"ok", {"status": 200})]

    with patch("src.ingest.service.CONNECTORS", {"web": MagicMock(discover=MagicMock(return_value=[{"url": "http://ok"}, {"url": "http://bad"}]), fetch=MagicMock(side_effect=fetch))}), patch(
        "src.ingest.service.get_thread_shard", return_value=_ImmediateShard()
    ), patch.object(service, "_run_condensation_task") as mock_condense:
        run = service.run_job(job.id)

    assert run.status == "partially_failed"
    assert run.stats["fetch_failures"] == 1
    assert "boom" in run.error_log
    mock_condense.assert_called_once()


def test_run_job_marks_failed_when_all_fetches_fail(mock_db):
    service = IngestService(mock_db)
    job = IngestJob(
        id=uuid.uuid4(),
        source_type="web",
        source_config={"urls": ["http://bad"]},
        state="active",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = job
    mock_db.execute.return_value.all.return_value = []

    def fetch(_config, _item_ref):
        raise RuntimeError("boom")

    with patch("src.ingest.service.CONNECTORS", {"web": MagicMock(discover=MagicMock(return_value=[{"url": "http://bad"}]), fetch=MagicMock(side_effect=fetch))}), patch(
        "src.ingest.service.get_thread_shard", return_value=_ImmediateShard()
    ), patch.object(service, "_run_condensation_task") as mock_condense:
        run = service.run_job(job.id)

    assert run.status == "failed"
    assert run.stats["fetch_failures"] == 1
    assert run.stats["fetched"] == 0
    mock_condense.assert_not_called()


class _TrackingFuture(Future):
    def __init__(self, tracker):
        super().__init__()
        self._tracker = tracker

    def result(self, timeout=None):
        self._tracker["consumed"] += 1
        return super().result(timeout=timeout)


class _TrackingShard:
    current_workers = 2

    def __init__(self):
        self.tracker = {"submits": 0, "consumed": 0}

    def submit(self, fn, *args, **kwargs):
        if getattr(fn, "__name__", "") == "_fetch_one":
            self.tracker["submits"] += 1
            if self.tracker["submits"] > self.current_workers and self.tracker["consumed"] == 0:
                raise AssertionError("submitted more than the worker cap before consuming results")
        future = _TrackingFuture(self.tracker)
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


def test_run_job_limits_fetches_in_flight(mock_db):
    service = IngestService(mock_db)
    job = IngestJob(
        id=uuid.uuid4(),
        source_type="web",
        source_config={"urls": [f"http://example.com/{i}" for i in range(5)]},
        state="active",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = job
    mock_db.execute.return_value.all.return_value = []
    shard = _TrackingShard()

    mock_connector = MagicMock()
    mock_connector.discover.return_value = [{"url": f"http://example.com/{i}"} for i in range(5)]
    mock_connector.fetch.side_effect = lambda _config, item_ref: [
        (item_ref["url"], b"payload", {"status": 200})
    ]

    with patch("src.ingest.service.CONNECTORS", {"web": mock_connector}), patch(
        "src.ingest.service.get_thread_shard", return_value=shard
    ), patch.object(service, "_run_condensation_task"):
        run = service.run_job(job.id)

    assert run.status == "completed"
    assert shard.tracker["submits"] == 5
