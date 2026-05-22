import os
from typing import List, Dict, Any, Generator, Tuple
from .base import Connector

class CodebaseConnector(Connector):
    # Standard source file extensions to index
    DEFAULT_EXTENSIONS = {
        '.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.toml', '.yaml', 
        '.yml', '.md', '.txt', '.rs', '.go', '.java', '.cpp', '.c', 
        '.h', '.hpp', '.cs', '.sh', '.bat', '.sql', '.ini', '.cfg'
    }

    # Standard directory names and files to completely ignore during traversal
    DEFAULT_IGNORE_PATTERNS = {
        '.git', 'node_modules', 'venv', '.venv', '__pycache__', 'dist', 
        'build', 'target', '.pytest_cache', '.gemini', 'package-lock.json', 
        'pnpm-lock.yaml', 'yarn.lock'
    }

    def discover(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recursively walks the target directory path and lists eligible source files.
        """
        path = config.get("path")
        if not path:
            raise ValueError("Config key 'path' must be specified for codebase ingestion.")

        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Codebase path does not exist: {path}")

        max_size = config.get("max_file_size", 64 * 1024) # Default 64KB
        allowed_extensions = set(config.get("allowed_extensions", self.DEFAULT_EXTENSIONS))
        ignore_patterns = set(config.get("ignore_patterns", self.DEFAULT_IGNORE_PATTERNS))

        discovered_files = []

        for root, dirs, files in os.walk(path):
            # Prune directory tree in-place to avoid walking down ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]

            for file in files:
                if file in ignore_patterns:
                    continue

                _, ext = os.path.splitext(file)
                if ext.lower() not in allowed_extensions:
                    continue

                full_path = os.path.join(root, file)

                # Check file size before scheduling discovery
                try:
                    size = os.path.getsize(full_path)
                    if size <= max_size:
                        discovered_files.append({"path": full_path})
                except OSError:
                    # Ignore unreadable files
                    continue

        return discovered_files

    def fetch(self, config: Dict[str, Any], item_ref: Dict[str, Any]) -> Generator[Tuple[str, bytes, Dict[str, Any]], None, None]:
        """
        Reads the specified source file, verifies it's not binary, and yields its bytes.
        """
        file_path = item_ref.get("path")
        if not file_path:
            return

        base_path = os.path.abspath(config.get("path"))

        try:
            # Open file in binary mode
            with open(file_path, "rb") as f:
                content = f.read()

            # Verify it is not binary (check for null byte in header)
            if b'\x00' in content[:1024]:
                return

            relative_path = os.path.relpath(file_path, base_path)
            _, ext = os.path.splitext(file_path)

            metadata = {
                "source": "codebase",
                "file_name": os.path.basename(file_path),
                "extension": ext,
                "size_bytes": len(content),
                "relative_path": relative_path,
            }

            yield (file_path, content, metadata)

        except Exception as e:
            # Swallow read failures for individual files to keep ingestion moving
            print(f"Failed to fetch codebase file {file_path}: {e}")
