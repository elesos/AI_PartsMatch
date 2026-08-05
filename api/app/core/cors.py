from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.database import SessionLocal
from app.services.config_service import ConfigService

ALLOWED_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOWED_HEADERS = "Accept, Authorization, Content-Type, X-Request-Id, X-Session-Id"


class DatabaseCORSMiddleware:
    """Strict credentialed CORS whose exact origin allowlist lives in sys_configs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _allowed_origins() -> set[str]:
        try:
            with SessionLocal() as db:
                values = ConfigService(db).get("security.cors_allowed_origins", [])
            return {value.rstrip("/") for value in values if isinstance(value, str)} if isinstance(values, list) else set()
        except Exception:
            return set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        if not origin:
            await self.app(scope, receive, send)
            return
        allowed = origin.rstrip("/") in self._allowed_origins()
        is_preflight = scope["method"] == "OPTIONS" and "access-control-request-method" in headers
        if is_preflight:
            if not allowed:
                await PlainTextResponse("CORS origin denied", status_code=400)(scope, receive, send)
                return
            response_headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": ALLOWED_METHODS,
                "Access-Control-Allow-Headers": ALLOWED_HEADERS,
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            }
            await Response(status_code=204, headers=response_headers)(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if allowed and message["type"] == "http.response.start":
                mutable = MutableHeaders(scope=message)
                mutable["Access-Control-Allow-Origin"] = origin
                mutable["Access-Control-Allow-Credentials"] = "true"
                mutable.add_vary_header("Origin")
            await send(message)

        await self.app(scope, receive, send_with_cors)
