from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int | str = 0
    message: str = "ok"
    data: T


def success(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data if data is not None else {}}
