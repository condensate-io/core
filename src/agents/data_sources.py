import httpx
import os
import logging
from src.db.models import DataSource

logger = logging.getLogger("DataSources")

async def fetch_source_data(source: DataSource) -> str:
    """
    Fetches content from a DataSource based on its type.
    """
    if source.source_type == "url":
        url = source.configuration.get("url")
        if not url:
            raise ValueError("Missing 'url' in configuration")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                # Use BeautifulSoup to extract text
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text(separator=' ', strip=True)
                return text

            except Exception as e:
                logger.error(f"Failed to fetch URL {url}: {e}")
                raise e

    elif source.source_type == "file":
        path = source.configuration.get("path")
        if not path:
            raise ValueError("Missing 'path' in configuration")
        
        # Security check: Ensure path is within allowed directories? 
        # For a local tool running in Docker, we assume mounted volumes.
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            raise e

    elif source.source_type == "api":
         # Generic API GET
        url = source.configuration.get("url")
        headers = source.configuration.get("headers", {})
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text

    else:
        raise ValueError(f"Unsupported source type: {source.source_type}")
