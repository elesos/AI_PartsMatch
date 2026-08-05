from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import AdminRefreshToken, AdminUser

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 480
REFRESH_TTL_DAYS = 14
REFRESH_COOKIE = "partsmatch_admin_refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user: AdminUser) -> tuple[str, int]:
    seconds = TOKEN_TTL_MINUTES * 60
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(UTC) + timedelta(seconds=seconds),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM), seconds


def create_refresh_token(db: Session, user: AdminUser) -> tuple[str, int]:
    raw = token_urlsafe(48)
    seconds = REFRESH_TTL_DAYS * 24 * 60 * 60
    db.add(AdminRefreshToken(token_hash=sha256(raw.encode()).hexdigest(), user_id=user.id,
                             expires_at=datetime.now(UTC) + timedelta(seconds=seconds)))
    db.commit()
    return raw, seconds


def rotate_refresh_token(db: Session, raw: str | None) -> tuple[AdminUser, str, int] | None:
    if not raw or len(raw) > 200:
        return None
    item = db.query(AdminRefreshToken).filter_by(token_hash=sha256(raw.encode()).hexdigest()).with_for_update().one_or_none()
    now = datetime.now(UTC)
    if item is None:
        return None
    expires_at = item.expires_at if item.expires_at.tzinfo else item.expires_at.replace(tzinfo=UTC)
    if item.revoked_at is not None or expires_at <= now:
        return None
    user = db.get(AdminUser, item.user_id)
    if user is None or not user.is_active or user.role not in {"admin", "operator"}:
        item.revoked_at = now; db.commit(); return None
    item.revoked_at = now
    next_raw = token_urlsafe(48)
    seconds = REFRESH_TTL_DAYS * 24 * 60 * 60
    db.add(AdminRefreshToken(token_hash=sha256(next_raw.encode()).hexdigest(), user_id=user.id,
                             expires_at=now + timedelta(seconds=seconds)))
    db.commit()
    return user, next_raw, seconds


def revoke_refresh_token(db: Session, raw: str | None) -> None:
    if raw and len(raw) <= 200:
        item = db.query(AdminRefreshToken).filter_by(token_hash=sha256(raw.encode()).hexdigest()).one_or_none()
        if item is not None and item.revoked_at is None:
            item.revoked_at = datetime.now(UTC)
            db.commit()


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as error:
        raise HTTPException(status_code=401, detail="invalid or expired token") from error
    user = db.get(AdminUser, user_id) if user_id else None
    if user is None or not user.is_active or user.role not in {"admin", "operator"}:
        raise HTTPException(status_code=401, detail="invalid administrator")
    return user


def require_role(*roles: Literal["admin", "operator"]):
    def dependency(user: Annotated[AdminUser, Depends(get_current_admin)]) -> AdminUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="insufficient permissions")
        return user
    return dependency


def require_admin_write(request: Request, user: Annotated[AdminUser, Depends(get_current_admin)]) -> AdminUser:
    """Operators may inspect catalog data, but all catalog mutations remain admin-only."""
    if request.method not in {"GET", "HEAD", "OPTIONS"} and user.role != "admin":
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return user


def get_session_id(x_session_id: Annotated[str | None, Header()] = None) -> str:
    return x_session_id or str(uuid4())
