import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, MagicMock

def test_app_startup_shutdown():
    """
    Test that the application starts up and shuts down correctly.
    This verifies that the lifespan context manager runs without errors.
    """
    # We need to mock start_scheduler and init_db to avoid side effects
    # and to ensure we are only testing the wiring in main.py
    with patch("main.start_scheduler") as mock_start, \
         patch("main.init_db") as mock_init:
        
        with TestClient(app) as client:
            # Entering the context manager triggers the startup event
            mock_init.assert_called_once()
            mock_start.assert_called_once()
            
            # Perform a health check (or simple root request)
            response = client.get("/docs")
            assert response.status_code == 200
            
    # Exiting the context manager triggers the shutdown event (if any)
