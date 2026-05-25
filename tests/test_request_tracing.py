import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.server.middleware.request_context import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    bind_request_id_logging,
    get_request_id,
)


@pytest.fixture
def tracing_client():
    bind_request_id_logging()
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    def ping():
        return {"request_id": get_request_id()}

    return TestClient(app)


def test_generates_request_id_when_missing(tracing_client):
    response = tracing_client.get("/ping")
    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id
    assert response.json()["request_id"] == request_id


def test_echoes_provided_request_id(tracing_client):
    provided_id = "test-correlation-id-12345"
    response = tracing_client.get("/ping", headers={REQUEST_ID_HEADER: provided_id})
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER) == provided_id
    assert response.json()["request_id"] == provided_id


def test_request_id_bound_to_logging_context(tracing_client):
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("test.request_tracing")
    handler = CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    @tracing_client.app.get("/log")
    def log_route():
        logging.getLogger("test.request_tracing").info("during request")
        return {"ok": True}

    provided_id = "logging-context-id-67890"
    response = tracing_client.get("/log", headers={REQUEST_ID_HEADER: provided_id})
    assert response.status_code == 200
    assert len(records) == 1
    assert getattr(records[0], "request_id") == provided_id

    logger.removeHandler(handler)
