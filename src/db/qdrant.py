import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.engine.embedding import get_embedding_dimension

logger = logging.getLogger("QdrantInit")

def init_qdrant(client: QdrantClient):
    """
    Ensure required collections exist in Qdrant.
    """
    embedding_dimension = get_embedding_dimension()
    collections = {
        "episodic_chunks": embedding_dimension,
        "semantic_assertions": embedding_dimension,
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
