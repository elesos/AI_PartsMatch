from typing import Annotated

from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, success
from app.core.security import (REFRESH_COOKIE, create_access_token, create_refresh_token, get_current_admin,
                               hash_password, require_role, revoke_refresh_token, rotate_refresh_token,
                               verify_password)
from app.models import AdminRefreshToken, AdminUser
from app.schemas.auth import (AdminIdentity, AdminPasswordReset, AdminUserCreate, AdminUserResult,
                              AdminUserUpdate, ChangePasswordRequest, LoginRequest, TokenResult)
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


def _user_result(user: AdminUser) -> dict:
    return AdminUserResult.model_validate(user, from_attributes=True).model_dump()


def _invalidate_sessions(db: Session, user: AdminUser) -> None:
    user.auth_version += 1
    db.query(AdminRefreshToken).filter(
        AdminRefreshToken.user_id == user.id,
        AdminRefreshToken.revoked_at.is_(None),
    ).update({AdminRefreshToken.revoked_at: datetime.now(UTC)}, synchronize_session=False)


def _active_admin_count(db: Session) -> int:
    return db.query(func.count(AdminUser.id)).filter(
        AdminUser.role == "admin", AdminUser.is_active.is_(True)
    ).scalar() or 0


@router.post("/auth/change-password", status_code=204, summary="Change current administrator password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AdminUser, Depends(get_current_admin)],
) -> Response:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="new password must be different")
    user.password_hash = hash_password(payload.new_password)
    _invalidate_sessions(db, user)
    db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/admin/auth")
    response.status_code = 204
    return response


@router.get("/users", response_model=ApiResponse[list[AdminUserResult]], summary="List administrator users")
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("admin"))],
) -> dict:
    users = db.query(AdminUser).order_by(AdminUser.created_at, AdminUser.username).all()
    return success([_user_result(user) for user in users])


@router.post("/users", response_model=ApiResponse[AdminUserResult], status_code=201,
             summary="Create administrator user")
def create_user(
    payload: AdminUserCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("admin"))],
) -> dict:
    user = AdminUser(username=payload.username, password_hash=hash_password(payload.password),
                     role=payload.role, is_active=payload.is_active)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="username already exists") from error
    db.refresh(user)
    return success(_user_result(user))


@router.put("/users/{user_id}", response_model=ApiResponse[AdminUserResult], summary="Update administrator user")
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[AdminUser, Depends(require_role("admin"))],
) -> dict:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    removes_active_admin = user.role == "admin" and user.is_active and (
        payload.role != "admin" or not payload.is_active
    )
    if removes_active_admin and _active_admin_count(db) <= 1:
        raise HTTPException(status_code=409, detail="at least one active administrator is required")
    if user.id == actor.id and (payload.role != "admin" or not payload.is_active):
        raise HTTPException(status_code=409, detail="you cannot remove your own administrator access")
    identity_changed = user.id != actor.id and (
        user.username != payload.username or user.role != payload.role or user.is_active != payload.is_active
    )
    user.username, user.role, user.is_active = payload.username, payload.role, payload.is_active
    if identity_changed:
        _invalidate_sessions(db, user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="username already exists") from error
    db.refresh(user)
    return success(_user_result(user))


@router.post("/users/{user_id}/reset-password", status_code=204, summary="Reset administrator user password")
def reset_user_password(
    user_id: str,
    payload: AdminPasswordReset,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[AdminUser, Depends(require_role("admin"))],
) -> Response:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="use change password for your own account")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="new password must be different")
    user.password_hash = hash_password(payload.new_password)
    _invalidate_sessions(db, user)
    db.commit()
    response.status_code = 204
    return response


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
