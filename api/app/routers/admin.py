from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, success
from app.core.security import (REFRESH_COOKIE, create_access_token, create_refresh_token, get_current_admin,
                               require_role, revoke_refresh_token, rotate_refresh_token, verify_password)
from app.models import AdminUser
from app.schemas.auth import AdminIdentity, LoginRequest, TokenResult
from app.schemas.configs import ConfigResult, ConfigUpsert
from app.services.config_service import ConfigService

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/auth/login", response_model=ApiResponse[TokenResult], summary="Administrator login")
def login(payload: LoginRequest, request: Request, response: Response,
          db: Annotated[Session, Depends(get_db)]) -> dict:
    user = db.query(AdminUser).filter(AdminUser.username == payload.username).one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")
    token, expires_in = create_access_token(user)
    refresh_token, refresh_expires = create_refresh_token(db, user)
    _set_refresh_cookie(response, request, refresh_token, refresh_expires)
    return success(TokenResult(access_token=token, expires_in=expires_in, role=user.role).model_dump())


def _set_refresh_cookie(response: Response, request: Request, token: str, max_age: int) -> None:
    response.set_cookie(REFRESH_COOKIE, token, max_age=max_age, httponly=True,
                        secure=request.url.hostname not in {"localhost", "127.0.0.1", "testserver"},
                        samesite="lax", path="/api/v1/admin/auth")


@router.post("/auth/refresh", response_model=ApiResponse[TokenResult], summary="Rotate administrator session")
def refresh(request: Request, response: Response, db: Annotated[Session, Depends(get_db)],
            refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None) -> dict:
    rotated = rotate_refresh_token(db, refresh_token)
    if rotated is None:
        response.delete_cookie(REFRESH_COOKIE, path="/api/v1/admin/auth")
        raise HTTPException(status_code=401, detail="invalid or expired refresh session")
    user, next_refresh, refresh_expires = rotated
    _set_refresh_cookie(response, request, next_refresh, refresh_expires)
    token, expires_in = create_access_token(user)
    return success(TokenResult(access_token=token, expires_in=expires_in, role=user.role).model_dump())


@router.post("/auth/logout", status_code=204, summary="End administrator session")
def logout(response: Response, db: Annotated[Session, Depends(get_db)],
           refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None) -> Response:
    revoke_refresh_token(db, refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/admin/auth")
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=ApiResponse[AdminIdentity], summary="Current administrator")
def me(user: Annotated[AdminUser, Depends(get_current_admin)]) -> dict:
    return success(AdminIdentity.model_validate(user, from_attributes=True).model_dump())


@router.get("/configs", response_model=ApiResponse[list[ConfigResult]], summary="List runtime system settings")
def list_configs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("admin"))],
) -> dict:
    items = []
    for item in ConfigService(db).list():
        value = "********" if item.is_secret else item.value
        items.append(ConfigResult(key=item.key, value=value, description=item.description, is_secret=item.is_secret).model_dump())
    return success(items)


@router.put("/configs/{key}", response_model=ApiResponse[ConfigResult], summary="Create or update a runtime system setting")
def upsert_config(
    key: str,
    payload: ConfigUpsert,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("admin"))],
) -> dict:
    item = ConfigService(db).set(key, payload.value, description=payload.description, is_secret=payload.is_secret)
    value = "********" if item.is_secret else item.value
    return success(ConfigResult(key=item.key, value=value, description=item.description, is_secret=item.is_secret).model_dump())
