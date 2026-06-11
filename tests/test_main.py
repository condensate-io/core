from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from main import app, lifespan


def test_app_startup_shutdown():
    """Verify lifespan wiring without heavy startup (NER, Qdrant, stopwords)."""
    app.router.lifespan_context = lifespan

    mock_engine = MagicMock()
    mock_engine.extract_entities.return_value = []

    with patch("main.start_scheduler") as mock_start, \
         patch("main.init_db") as mock_init, \
         patch("qdrant_client.QdrantClient") as mock_qdrant_cls, \
         patch("src.db.qdrant.init_qdrant"), \
         patch("src.engine.stopwords.bootstrap_stop_words"), \
         patch("src.llm.bootstrap.bootstrap_llm", new_callable=AsyncMock), \
         patch("src.engine.ner.get_ner_engine", return_value=mock_engine):
        mock_qdrant_cls.return_value = MagicMock()

        with TestClient(app) as client:
            mock_init.assert_called_once()
            mock_start.assert_called_once()

            response = client.get("/docs")
            assert response.status_code == 200
