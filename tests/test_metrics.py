import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.server.metrics import PrometheusMiddleware
from src.server.metrics import router as metrics_router


@pytest.fixture
def metrics_client():
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)
    app.include_router(metrics_router)

    @app.get("/sample")
    def sample():
        return {"ok": True}

    return TestClient(app)


def test_metrics_endpoint_returns_prometheus_format(metrics_client):
    response = metrics_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_http_requests_recorded_in_metrics(metrics_client):
    metrics_client.get("/sample")
    metrics_client.get("/sample")

    response = metrics_client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert 'http_requests_total{method="GET",path="/sample",status_code="200"}' in body
    metric_lines = [
        line for line in body.splitlines() if line.startswith("http_requests_total{")
    ]
    assert not any('path="/metrics"' in line for line in metric_lines)
