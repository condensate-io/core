import time

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> StarletteResponse:
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = request.url.path
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        status_code = str(response.status_code)
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            path=path,
            status_code=status_code,
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
        return response
