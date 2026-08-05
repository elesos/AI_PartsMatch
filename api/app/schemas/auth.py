from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class TokenResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: Literal["admin", "operator"]


class AdminIdentity(BaseModel):
    id: str
    username: str
    role: Literal["admin", "operator"]
