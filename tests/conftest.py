import sys
import os
import pytest
from unittest.mock import MagicMock

# Add src to path for all tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(scope="function")
def db_session():
    return MagicMock()

@pytest.fixture
def project(db_session):
    return MagicMock(id="test-project-id")
