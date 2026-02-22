import pytest
import uuid
from unittest.mock import MagicMock, patch
from src.ingest.service import IngestService
from src.db.models import IngestJob, IngestJobRun, FetchedArtifact

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
        
        run = service.run_job(job.id)
        
        assert run.status == "completed"
        # 1 run + 1 artifact added
        assert mock_db.add.call_count >= 2 
