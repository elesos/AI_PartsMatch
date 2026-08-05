from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import REFRESH_COOKIE, create_access_token, hash_password
from app.main import app
from app.models import AdminRefreshToken, AdminUser, Base

engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def override_db():
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def setup_module() -> None:
    with TestingSession() as db:
        if not db.query(AdminUser).filter_by(username="admin").first():
            db.add(AdminUser(username="admin", password_hash=hash_password("test-password"), role="admin"))
            db.add(AdminUser(username="operator", password_hash=hash_password("test-password"), role="operator"))
            db.commit()


def test_admin_route_requires_login() -> None:
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_login_and_access_protected_route() -> None:
    response = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "test-password"})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    me = client.get("/api/v1/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["data"]["role"] == "admin"


def test_refresh_cookie_is_httponly_rotated_and_revocable() -> None:
    response = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "test-password"})
    assert "httponly" in response.headers["set-cookie"].lower()
    old_refresh = client.cookies.get(REFRESH_COOKIE)
    refreshed = client.post("/api/v1/admin/auth/refresh")
    assert refreshed.status_code == 200
    next_refresh = client.cookies.get(REFRESH_COOKIE)
    assert old_refresh and next_refresh and old_refresh != next_refresh
    with TestingSession() as db:
        rows = db.query(AdminRefreshToken).order_by(AdminRefreshToken.created_at).all()
        assert any(row.revoked_at is not None for row in rows)
        assert all(row.token_hash not in {old_refresh, next_refresh} for row in rows)
    replay = TestClient(app)
    replay.cookies.set(REFRESH_COOKIE, old_refresh, path="/api/v1/admin/auth")
    assert replay.post("/api/v1/admin/auth/refresh").status_code == 401
    assert client.post("/api/v1/admin/auth/logout").status_code == 204
    assert client.post("/api/v1/admin/auth/refresh").status_code == 401


def test_access_and_refresh_credentials_are_not_interchangeable() -> None:
    login_response = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "test-password"})
    access = login_response.json()["data"]["access_token"]
    no_cookie = TestClient(app)
    no_cookie.cookies.set(REFRESH_COOKIE, access, path="/api/v1/admin/auth")
    assert no_cookie.post("/api/v1/admin/auth/refresh").status_code == 401
    refresh = client.cookies.get(REFRESH_COOKIE)
    assert client.get("/api/v1/admin/auth/me", headers={"Authorization": f"Bearer {refresh}"}).status_code == 401


def test_operator_can_read_catalog_but_cannot_mutate_it() -> None:
    with TestingSession() as db:
        operator = db.query(AdminUser).filter_by(username="operator").one()
        token, _ = create_access_token(operator)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/parts", headers=headers).status_code == 200
    denied = client.post("/api/v1/admin/parts", headers=headers, json={})
    assert denied.status_code == 403
