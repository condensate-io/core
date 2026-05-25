import pytest
import os
import uuid
import tempfile
from unittest.mock import MagicMock, patch
from src.ingest.connectors.codebase import CodebaseConnector
from src.ingest.service import IngestService
from src.db.models import IngestJob, IngestJobRun, FetchedArtifact

@pytest.fixture
def temp_codebase_dir():
    """
    Creates a temporary directory with various files (valid, binary, large, ignored)
    to test the CodebaseConnector's discovery and filtering capabilities.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Valid files
        with open(os.path.join(tmpdir, "main.py"), "w", encoding="utf-8") as f:
            f.write("def hello():\n    print('Hello World')")

        with open(os.path.join(tmpdir, "README.md"), "w", encoding="utf-8") as f:
            f.write("# Temp Project\nThis is a test repo.")

        # 2. Ignored directories and files within them
        node_modules_dir = os.path.join(tmpdir, "node_modules")
        os.makedirs(node_modules_dir)
        with open(os.path.join(node_modules_dir, "lodash.js"), "w", encoding="utf-8") as f:
            f.write("console.log('ignored');")

        # 3. Ignored file name
        with open(os.path.join(tmpdir, "package-lock.json"), "w", encoding="utf-8") as f:
            f.write("{}")

        # 4. Non-allowed extension
        with open(os.path.join(tmpdir, "image.png"), "w", encoding="utf-8") as f:
            f.write("not-a-real-png-data")

        # 5. Large file (exceeding default 64KB limit)
        with open(os.path.join(tmpdir, "giant.py"), "w", encoding="utf-8") as f:
            f.write("a" * (70 * 1024)) # 70KB

        # 6. Binary file (containing null byte)
        with open(os.path.join(tmpdir, "binary_file.txt"), "wb") as f:
            f.write(b"Some text\x00with null byte")

        yield tmpdir

def test_codebase_discovery(temp_codebase_dir):
    connector = CodebaseConnector()
    config = {"path": temp_codebase_dir}

    discovered = connector.discover(config)
    paths = [item["path"] for item in discovered]

    # Should discover main.py and README.md
    assert any(p.endswith("main.py") for p in paths)
    assert any(p.endswith("README.md") for p in paths)

    # Should NOT discover node_modules, package-lock.json, image.png, giant.py
    assert not any("node_modules" in p for p in paths)
    assert not any(p.endswith("package-lock.json") for p in paths)
    assert not any(p.endswith("image.png") for p in paths)
    assert not any(p.endswith("giant.py") for p in paths)
    
    # Binary file txt might be discovered here because size <= 64KB (its contents are filtered at fetch time)
    assert any(p.endswith("binary_file.txt") for p in paths)

def test_codebase_fetch(temp_codebase_dir):
    connector = CodebaseConnector()
    config = {"path": temp_codebase_dir}

    # Fetch a valid file
    main_py_path = os.path.join(temp_codebase_dir, "main.py")
    results = list(connector.fetch(config, {"path": main_py_path}))
    
    assert len(results) == 1
    uri, content, meta = results[0]
    assert uri == main_py_path
    assert b"def hello()" in content
    assert meta["source"] == "codebase"
    assert meta["file_name"] == "main.py"
    assert meta["extension"] == ".py"
    assert meta["relative_path"] == "main.py"

    # Fetch a binary file (should be filtered out and yield nothing)
    binary_path = os.path.join(temp_codebase_dir, "binary_file.txt")
    binary_results = list(connector.fetch(config, {"path": binary_path}))
    assert len(binary_results) == 0

def test_service_codebase_ingest_integration(temp_codebase_dir):
    mock_db = MagicMock()
    service = IngestService(mock_db)

    # Mock an ingestion job
    job = IngestJob(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_type="codebase",
        source_config={"path": temp_codebase_dir},
        state="active"
    )

    mock_db.query.return_value.filter.return_value.first.return_value = job

    # We patch the background thread in the service to avoid spawning async threads in the test
    with patch.object(service, "_run_condensation_task") as mock_condense:
        run = service.run_job(job.id)

        assert run.status == "completed"
        assert run.stats["fetched"] >= 2 # main.py and README.md
        
        # Verify db.add is called for the IngestJobRun and the FetchedArtifact rows
        assert mock_db.add.call_count >= 3
        mock_condense.assert_called_once()
