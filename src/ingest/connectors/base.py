from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator, Tuple

class Connector(ABC):
    @abstractmethod
    def discover(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Lists available resources to fetch.
        For Web, maybe just the seed URL or sitemap entries.
        For Chroma, list of collection IDs.
        """
        pass

    @abstractmethod
    def fetch(self, config: Dict[str, Any], item_ref: Dict[str, Any]) -> Generator[Tuple[str, bytes, Dict[str, Any]], None, None]:
        """
        Yields (source_uri, content_bytes, metadata).
        """
        pass
