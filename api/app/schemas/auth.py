from datetime import datetime
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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    password: str = Field(min_length=8, max_length=200)
    role: Literal["admin", "operator"] = "operator"
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    role: Literal["admin", "operator"]
    is_active: bool


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


class AdminUserResult(BaseModel):
    id: str
    username: str
    role: Literal["admin", "operator"]
    is_active: bool
    created_at: datetime
    updated_at: datetime
