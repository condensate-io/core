
import pytest
import uuid
import time
import sys
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from src.db.models import IngestJob

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)

def test_run_job_is_async(mock_db):
    # Setup
    job_id = uuid.uuid4()
    job = IngestJob(id=job_id, source_type="web", source_config={"url": "http://example.com"})
    mock_db.query.return_value.filter.return_value.first.return_value = job
    
    # Mock connector to return immediately with some data
    mock_connector = MagicMock()
    mock_connector.discover.return_value = ["ref1"]
    mock_connector.fetch.return_value = [("http://example.com", b"content", {})]
    
    # Use patch.dict to avoid leaking to other tests
    with patch.dict(sys.modules, {
        'src.agents.ingress': MagicMock(),
        'qdrant_client': MagicMock()
    }):
        # Delay import of service to ensure mocks apply
        from src.ingest.service import IngestService
        service = IngestService(mock_db)
        
        with patch("src.ingest.service.CONNECTORS", {"web": mock_connector}):
            with patch("src.ingest.service.threading.Thread") as MockThread:
                # Execute
                start_time = time.time()
                run = service.run_job(job_id)
                end_time = time.time()
                
                # Verify
                assert (end_time - start_time) < 1.0, "run_job took too long, arguably blocking"
                assert run.status == "completed" # Ingestion part is completed
                
                # Verify thread was started for condensation
                MockThread.assert_called_once()
                _, kwargs = MockThread.call_args
                assert kwargs['target'] == service._run_condensation_task
                MockThread.return_value.start.assert_called_once()
