import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.engine.scheduler import schedule_data_source, trigger_data_source, process_data_source
from src.db.models import DataSource
import uuid

# Mock the database session and other dependencies
@pytest.fixture
def mock_db_session():
    with patch("src.engine.scheduler.SessionLocal") as mock:
        yield mock

@pytest.fixture
def mock_scheduler():
    with patch("src.engine.scheduler.scheduler") as mock:
        yield mock

def test_schedule_data_source(mock_scheduler):
    ds = DataSource(
        id=uuid.uuid4(),
        name="Test Source",
        enabled=True,
        cron_schedule="0 0 * * *"
    )
    
    schedule_data_source(ds)
    
    # Verify add_job was called
    mock_scheduler.add_job.assert_called()
    args, kwargs = mock_scheduler.add_job.call_args
    assert kwargs['id'] == str(ds.id)
    assert kwargs['replace_existing'] == True

def test_trigger_data_source(mock_scheduler):
    sid = uuid.uuid4()
    trigger_data_source(sid)
    
    mock_scheduler.add_job.assert_called()
    mock_scheduler.add_job.assert_called()
    args, kwargs = mock_scheduler.add_job.call_args
    assert args[0] == process_data_source
    assert kwargs['args'][0] == sid

@pytest.mark.asyncio
async def test_process_data_source(mock_db_session):
    # Setup mock DB
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
    sid = uuid.uuid4()
    pid = uuid.uuid4()
    source = DataSource(
        id=sid,
        project_id=pid,
        name="Test Source",
        source_type="url",
        enabled=True,
        configuration={"url": "http://test.com"}
    )
    mock_db.query.return_value.filter.return_value.first.return_value = source
    
    # Mock dependencies
    # Mock dependencies
    with patch("src.engine.scheduler.fetch_source_data", new_callable=MagicMock) as mock_fetch, \
         patch("src.engine.scheduler.IngressAgent") as MockIngress, \
         patch("src.engine.scheduler.QdrantClient"), \
         patch("src.engine.scheduler.Condenser") as MockCondenser:
        
        # Make fetch return an awaitable
        f = asyncio.Future()
        f.set_result("Mock Content")
        mock_fetch.return_value = f

        # Make CondensationAgent.run awaitable
        # Make Condenser.distill awaitable
        mock_condenser_instance = MockCondenser.return_value
        distill_future = asyncio.Future()
        distill_future.set_result(None)
        mock_condenser_instance.distill.return_value = distill_future
        
        await process_data_source(sid)
        
        # Assertions
        mock_fetch.assert_called_once_with(source)
        MockIngress.return_value.process_memory.assert_called()
        mock_condenser_instance.distill.assert_called_once()
        assert source.last_run is not None
