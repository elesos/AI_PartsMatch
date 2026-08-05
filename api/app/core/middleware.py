import logging
import time
import uuid

from fastapi import FastAPI, Request

logger = logging.getLogger("partsmatch.requests")


def install_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        logger.info(
            "%s %s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
            request_id,
        )
        return response
