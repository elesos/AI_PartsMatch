import os
from pathlib import Path

from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models import AdminUser


def secret_or_input(name: str, default: str) -> str:
    path = Path("/run/secrets") / name.lower()
    return path.read_text(encoding="utf-8").strip() if path.is_file() else os.environ.get(name, default)


def main() -> None:
    username = secret_or_input("ADMIN_INITIAL_USERNAME", "admin")
    password = secret_or_input("ADMIN_INITIAL_PASSWORD", "admin-local-only")
    with SessionLocal() as db:
        user = db.query(AdminUser).filter(AdminUser.username == username).one_or_none()
        if user is None:
            db.add(AdminUser(username=username, password_hash=hash_password(password), role="admin"))
            db.commit()
        elif not verify_password(password, user.password_hash):
            # The mounted bootstrap secret remains the recovery credential for this reserved account.
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
            db.commit()


if __name__ == "__main__":
    main()
