from qdrant_client import QdrantClient
from qdrant_client.http import models
import logging

logger = logging.getLogger("QdrantInit")

def init_qdrant(client: QdrantClient):
    """
    Ensure required collections exist in Qdrant.
    """
    collections = {
        "episodic_chunks": 384, # Default FastEmbed dimension
        "semantic_assertions": 384 # Assuming same model for now
    }
    
    existing = client.get_collections().collections
    existing_names = [c.name for c in existing]
    
    for name, dim in collections.items():
        if name not in existing_names:
            logger.info(f"Creating Qdrant collection: {name}")
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=dim,
                    distance=models.Distance.COSINE
                )
            )
        else:
            logger.info(f"Qdrant collection {name} exists.")
