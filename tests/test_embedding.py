import threading
import time
from unittest.mock import MagicMock, patch

from src.engine.embedding import (
    get_embedding_dimension,
    get_embedding_model,
    reset_embedding_model,
)


def test_get_embedding_model_is_thread_safe():
    reset_embedding_model()
    start_barrier = threading.Barrier(2)
    embedding_instance = MagicMock()
    embedding_instance.embedding_dimension = 384

    def build_model(*args, **kwargs):
        time.sleep(0.05)
        return embedding_instance

    with patch("src.engine.embedding.TextEmbedding", side_effect=build_model) as mock_cls:
        results = []

        def load():
            start_barrier.wait()
            results.append(get_embedding_model())

        t1 = threading.Thread(target=load)
        t2 = threading.Thread(target=load)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    reset_embedding_model()

    assert mock_cls.call_count == 1
    assert results == [embedding_instance, embedding_instance]


def test_get_embedding_dimension_uses_supported_model_metadata():
    reset_embedding_model()

    with patch("src.engine.embedding.get_embedding_model_name", return_value="custom-model"), patch(
        "src.engine.embedding._dimension_from_supported_models", return_value=768
    ), patch("src.engine.embedding.TextEmbedding") as mock_cls:
        assert get_embedding_dimension() == 768
        mock_cls.assert_not_called()

    reset_embedding_model()


def test_init_qdrant_uses_embedding_dimension():
    client = MagicMock()
    client.get_collections.return_value.collections = []

    with patch("src.db.qdrant.get_embedding_dimension", return_value=768):
        from src.db.qdrant import init_qdrant

        init_qdrant(client)

    created_sizes = [
        call.kwargs["vectors_config"].size
        for call in client.create_collection.call_args_list
    ]
    assert created_sizes == [768, 768]
