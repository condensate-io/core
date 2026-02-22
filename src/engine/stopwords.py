"""
src/engine/stopwords.py

Stop words management for the Condensate NER/extraction pipeline.

On cold start this module fetches the stopwords-iso/stopwords-en corpus
(~750 English stop words) and caches it locally so subsequent restarts
do not require a network call. The cached file is stored at
`data/stopwords_en.txt` inside the application root.

The public API is just one function:
    get_stop_words() -> frozenset[str]
"""

import logging
import os
import pathlib

logger = logging.getLogger("StopWords")

# ------------------------------------------------------------------
# Source and cache paths
# ------------------------------------------------------------------
CORPUS_URL = (
    "https://raw.githubusercontent.com/stopwords-iso/"
    "stopwords-en/master/stopwords-en.txt"
)

_APP_ROOT = pathlib.Path(os.getenv("APP_ROOT", "/app"))
_CACHE_FILE = _APP_ROOT / "data" / "stopwords_en.txt"

# ------------------------------------------------------------------
# Programming / code-noise additions
# These are domain-specific tokens that never appear in the ISO
# corpus but will flood a knowledge graph built from source code.
# ------------------------------------------------------------------
PROGRAMMING_NOISE: frozenset[str] = frozenset({
    # Python builtins
    "none", "true", "false", "self", "cls", "return", "yield",
    "import", "class", "def", "async", "await",
    "try", "except", "finally", "raise", "pass", "break", "continue",
    "print", "len", "str", "int", "float", "bool",
    "dict", "set", "tuple", "object", "super", "property", "staticmethod",
    # Generic single-concept code noise
    "b", "db", "os", "src", "rel", "app", "math", "uuid",
    "log", "data", "item", "items", "result", "results",
    "value", "values", "key", "keys", "names",
    "info", "error", "warning", "debug", "message", "msg",
    "types", "kind", "mode", "state", "status", "flag",
    "count", "total", "size", "index", "limit", "offset",
    "begin", "step",
    "min", "max", "avg", "sum",
    "url", "uri", "host", "port",
    "node", "edge", "graph", "tree", "root",
    "folder", "config", "env",
    "request", "response", "handler",
    "query", "filter", "sort", "order", "group",
    "test", "tests", "mock", "stub", "fixture",
    # SQLAlchemy / ORM noise
    "session", "engine", "model", "schema",
    "table", "column", "row", "record", "field",
    # Generic entity-type labels that NER sometimes extracts as entities
    "system", "concept", "artifact", "project", "tool",
    "localhost", "null",
})

# High-signal technical terms that SHOULD survive even if they look short
TECH_ALLOW_LIST: frozenset[str] = frozenset({
    "fastapi", "pydantic", "sqlalchemy", "qdrant",
    "gliner", "ollama", "phi3", "gpt-4",
    "kubernetes", "docker", "postgres", "postgresql", "redis",
    "oauth", "api", "auth",
    "backend", "frontend",
    "refactoring", "migration", "bottleneck", "latency",
    "roadmap",
})

# Minimum character length for a heuristically extracted entity.
# Entities shorter than this (and not in TECH_ALLOW_LIST) are pruned.
MIN_ENTITY_LENGTH = 3

# ------------------------------------------------------------------
# Internal cache
# ------------------------------------------------------------------
_STOP_WORDS: frozenset[str] | None = None


def _load_from_cache() -> frozenset[str] | None:
    """Return words from disk cache, or None if the cache doesn't exist."""
    if _CACHE_FILE.exists():
        try:
            raw = _CACHE_FILE.read_text(encoding="utf-8")
            words = {w.strip().lower() for w in raw.splitlines() if w.strip()}
            logger.info(f"[StopWords] Loaded {len(words)} words from cache {_CACHE_FILE}")
            return frozenset(words)
        except Exception as e:
            logger.warning(f"[StopWords] Failed to read cache: {e}")
    return None


def _fetch_remote() -> frozenset[str] | None:
    """Download the ISO corpus. Returns the word set, or None on error."""
    try:
        import urllib.request
        logger.info(f"[StopWords] Fetching corpus from {CORPUS_URL} ...")
        with urllib.request.urlopen(CORPUS_URL, timeout=10) as resp:
            text = resp.read().decode("utf-8")
        words = {w.strip().lower() for w in text.splitlines() if w.strip()}
        logger.info(f"[StopWords] Downloaded {len(words)} words.")
        return frozenset(words)
    except Exception as e:
        logger.error(f"[StopWords] Remote fetch failed: {e}")
        return None


def _save_to_cache(words: frozenset[str]) -> None:
    """Persist the word set to disk so future cold starts are fast."""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text("\n".join(sorted(words)), encoding="utf-8")
        logger.info(f"[StopWords] Cached {len(words)} words to {_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"[StopWords] Could not write cache: {e}")


def bootstrap_stop_words() -> None:
    """
    Called at cold-start (main.py lifespan).

    Tries to load from disk cache first. If absent it fetches the ISO
    corpus, merges with PROGRAMMING_NOISE, and caches to disk.
    """
    global _STOP_WORDS

    base = _load_from_cache()
    if base is None:
        base = _fetch_remote()
        if base:
            _save_to_cache(base)
        else:
            # Degraded mode: fall back to a minimal built-in set
            logger.warning("[StopWords] Using built-in fallback stop words.")
            base = frozenset({
                "a", "an", "the", "and", "or", "but", "in", "on",
                "at", "to", "for", "of", "with", "by", "from", "is",
                "are", "was", "were", "be", "been", "being", "have",
                "has", "had", "do", "does", "did", "will", "would",
                "could", "should", "may", "might", "shall", "can",
                "i", "you", "he", "she", "it", "we", "they", "this", "that",
            })

    _STOP_WORDS = base | PROGRAMMING_NOISE
    logger.info(
        f"[StopWords] Ready. Total stop words: {len(_STOP_WORDS)} "
        f"(ISO corpus + {len(PROGRAMMING_NOISE)} programming noise terms)"
    )


def get_stop_words() -> frozenset[str]:
    """
    Return the merged stop words set.

    If bootstrap_stop_words() has not been called yet (e.g. in a test
    context), it is called lazily on first access.
    """
    global _STOP_WORDS
    if _STOP_WORDS is None:
        bootstrap_stop_words()
    return _STOP_WORDS
