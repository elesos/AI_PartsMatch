from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, message: str, *, code: int | str = 40000, status_code: int = 400, data: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data or {}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "message": exc.message, "data": exc.data}, status_code=exc.status_code)

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        message = str(exc.detail)
        return JSONResponse(
            {"code": exc.status_code, "message": message, "data": {}},
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Validation inputs may contain UploadFile or other non-JSON objects.
        errors = [{key: error[key] for key in ("type", "loc", "msg") if key in error} for error in exc.errors()]
        return JSONResponse(
            {"code": 422, "message": "validation error", "data": {"errors": errors}},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse({"code": 500, "message": "internal server error", "data": {}}, status_code=500)
