import os
import shutil
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Use a temporary directory for uploads during tests to avoid polluting the workspace
@pytest.fixture(autouse=True)
def mock_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    return tmp_path

def test_upload_file(mock_upload_dir):
    filename = "test_upload.txt"
    content = b"Hello, World! This is a test file."
    
    # Create the file object to upload
    # We can pass a file-like object directly
    response = client.post(
        "/api/admin/upload",
        files={"file": (filename, content, "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == filename
    assert "path" in data
    
    uploaded_path = data["path"]
    
    # Verify file existence and content
    assert os.path.exists(uploaded_path)
    with open(uploaded_path, "rb") as f:
        assert f.read() == content
