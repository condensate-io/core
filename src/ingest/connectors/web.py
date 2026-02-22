import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Generator, Tuple
from .base import Connector

class WebURLConnector(Connector):
    def discover(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Simple version: just return the URLs in config
        urls = config.get("urls", [])
        return [{"url": u} for u in urls]

    def fetch(self, config: Dict[str, Any], item_ref: Dict[str, Any]) -> Generator[Tuple[str, bytes, Dict[str, Any]], None, None]:
        url = item_ref["url"]
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            
            # Simple metadata extraction
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string if soup.title else url
            
            metadata = {
                "source": "web",
                "title": title,
                "url": url,
                "status_code": resp.status_code
            }
            
            yield (url, resp.content, metadata)
            
        except Exception as e:
            # In a real system, we might yield an error artifact or log it
            print(f"Failed to fetch {url}: {e}")
            # Re-raise or handle? For now let's swallow and log to keep pipeline moving for other items? 
            # ideally the IngestJobRun catches this.
            raise e
