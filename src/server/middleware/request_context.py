import logging
import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

_record_factory_installed = False
_original_log_record_factory = logging.getLogRecordFactory()


def bind_request_id_logging() -> None:
    global _record_factory_installed
    if _record_factory_installed:
        return

    def factory(*args, **kwargs):
        record = _original_log_record_factory(*args, **kwargs)
        record.request_id = request_id_var.get() or "-"
        return record

    logging.setLogRecordFactory(factory)
    _record_factory_installed = True


def get_request_id() -> Optional[str]:
    return request_id_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_var.reset(token)
