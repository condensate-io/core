import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.db.models import DataSource
from src.agents.data_sources import fetch_source_data

@pytest.mark.asyncio
async def test_fetch_url():
    source = DataSource(source_type="url", configuration={"url": "http://example.com"})
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "Example Content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        content = await fetch_source_data(source)
        assert content == "Example Content"

@pytest.mark.asyncio
async def test_fetch_file(tmp_path):
    # Create temp file
    p = tmp_path / "test.txt"
    p.write_text("File Content", encoding="utf-8")
    
    source = DataSource(source_type="file", configuration={"path": str(p)})
    content = await fetch_source_data(source)
    assert content == "File Content"
