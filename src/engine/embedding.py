"""
Shared embedding model helper.

Both ingestion (src/agents/ingress.py) and retrieval (src/retrieve/router.py)
need a fastembed TextEmbedding instance. This module centralizes model
selection so ingest-time and query-time vectors are always produced by the
same model/dimensionality (avoiding silent Qdrant vector mismatches), and so
the (relatively expensive) ONNX model load happens exactly once per process
regardless of which entrypoint touches it first.
"""
import logging
import os
from typing import List

from fastembed import TextEmbedding

logger = logging.getLogger("Embedding")

_MODEL = None


def get_embedding_providers() -> List[str]:
    """Return ONNX execution providers, preferring GPU unless forced to CPU."""
    force_cpu = os.getenv("EMBEDDING_FORCE_CPU", "").lower() in ("1", "true", "yes")
    # Back-compat with the retrieval-side env var used before embedding config
    # was unified across ingest and query.
    force_cpu = force_cpu or os.getenv("RETRIEVE_EMBED_CPU", "").lower() in ("1", "true", "yes")
    if not force_cpu:
        try:
            from src.config import settings

            force_cpu = bool(settings.EMBEDDING_FORCE_CPU)
        except Exception:
            pass

    if not force_cpu:
        try:
            import onnxruntime as ort

            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                logger.info("Embedding: Using CUDAExecutionProvider (GPU)")
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except ImportError:
            pass

    logger.info("Embedding: Using CPUExecutionProvider")
    return ["CPUExecutionProvider"]


def get_embedding_model_name() -> str:
    name = os.getenv("EMBEDDING_MODEL")
    if name:
        return name
    try:
        from src.config import settings

        return settings.EMBEDDING_MODEL
    except Exception:
        return "BAAI/bge-small-en-v1.5"


def get_embedding_model():
    """
    Process-wide singleton fastembed TextEmbedding instance.

    Warmed once (lazily on first call, or eagerly via warm_embedding_model())
    and shared across ingest and retrieval code paths.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    model_name = get_embedding_model_name()
    providers = get_embedding_providers()
    logger.info("Loading embedding model %s (providers=%s)", model_name, providers)
    _MODEL = TextEmbedding(model_name=model_name, providers=providers)
    return _MODEL


def warm_embedding_model() -> None:
    """Eagerly load the embedding model at startup to avoid first-request latency."""
    try:
        get_embedding_model()
    except Exception as e:
        logger.warning("Embedding model warmup failed: %s", e)


def reset_embedding_model() -> None:
    """Clear the cached singleton. Primarily used by tests to force a reload."""
    global _MODEL
    _MODEL = None
