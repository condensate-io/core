import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.server.middleware.rate_limit import (
    RateLimitMiddleware,
    SlidingWindowRateLimiter,
)


@pytest.fixture
def rate_limited_client():
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        max_requests=3,
        window_seconds=60,
    )

    @app.get("/api/data")
    def api_data():
        return {"ok": True}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return "metrics"

    @app.get("/assets/app.js")
    def asset():
        return "console.log('ok')"

    return TestClient(app)


def test_requests_under_limit_succeed(rate_limited_client):
    for _ in range(3):
        response = rate_limited_client.get("/api/data")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


def test_exceeding_limit_returns_429_with_retry_after(rate_limited_client):
    for _ in range(3):
        assert rate_limited_client.get("/api/data").status_code == 200

    response = rate_limited_client.get("/api/data")
    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) >= 1


def test_exempt_paths_not_limited(rate_limited_client):
    for _ in range(10):
        assert rate_limited_client.get("/healthz").status_code == 200
        assert rate_limited_client.get("/health").status_code == 200
        assert rate_limited_client.get("/metrics").status_code == 200
        assert rate_limited_client.get("/assets/app.js").status_code == 200


def test_disabled_middleware_allows_unlimited_requests():
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        enabled=False,
        max_requests=1,
        window_seconds=60,
    )

    @app.get("/api/data")
    def api_data():
        return {"ok": True}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/api/data").status_code == 200


def test_separate_limits_per_client_ip():
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        max_requests=2,
        window_seconds=60,
    )

    @app.get("/api/data")
    def api_data():
        return {"ok": True}

    client = TestClient(app)
    assert (
        client.get("/api/data", headers={"X-Forwarded-For": "1.2.3.4"}).status_code
        == 200
    )
    assert (
        client.get("/api/data", headers={"X-Forwarded-For": "1.2.3.4"}).status_code
        == 200
    )
    assert (
        client.get("/api/data", headers={"X-Forwarded-For": "1.2.3.4"}).status_code
        == 429
    )

    assert (
        client.get("/api/data", headers={"X-Forwarded-For": "5.6.7.8"}).status_code
        == 200
    )


def test_sliding_window_retry_after_uses_oldest_timestamp():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10)
    assert limiter.check("client-a", now=100.0) == (True, 0)
    assert limiter.check("client-a", now=101.0) == (True, 0)
    allowed, retry_after = limiter.check("client-a", now=102.0)
    assert allowed is False
    assert retry_after == 9
