from fastapi import FastAPI

from src.config import settings
from src.server.metrics import PrometheusMiddleware
from src.server.metrics import router as metrics_router
from src.server.middleware.rate_limit import RateLimitMiddleware
from src.server.middleware.request_context import (
    RequestContextMiddleware,
    bind_request_id_logging,
)


def register_observability(app: FastAPI) -> None:
    bind_request_id_logging()
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.RATE_LIMIT_ENABLED,
        max_requests=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(metrics_router)
