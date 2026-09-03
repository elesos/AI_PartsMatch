from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import REFRESH_COOKIE, create_access_token, hash_password, verify_password
from app.main import app
from app.models import AdminRefreshToken, AdminUser, Base
from app.scripts import bootstrap_admin

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


def test_current_user_can_change_password_and_all_old_sessions_are_invalidated() -> None:
    with TestingSession() as db:
        user = AdminUser(username="password-owner", password_hash=hash_password("old-password"), role="operator")
        db.add(user); db.commit()
    first = TestClient(app)
    second = TestClient(app)
    first_login = first.post("/api/v1/admin/auth/login", json={"username": "password-owner", "password": "old-password"})
    second_login = second.post("/api/v1/admin/auth/login", json={"username": "password-owner", "password": "old-password"})
    first_token = first_login.json()["data"]["access_token"]
    second_token = second_login.json()["data"]["access_token"]
    changed = first.post("/api/v1/admin/auth/change-password", headers={"Authorization": f"Bearer {first_token}"},
                         json={"current_password": "old-password", "new_password": "new-password"})
    assert changed.status_code == 204
    assert second.get("/api/v1/admin/auth/me", headers={"Authorization": f"Bearer {second_token}"}).status_code == 401
    assert second.post("/api/v1/admin/auth/refresh").status_code == 401
    assert first.post("/api/v1/admin/auth/login", json={"username": "password-owner", "password": "old-password"}).status_code == 401
    assert first.post("/api/v1/admin/auth/login", json={"username": "password-owner", "password": "new-password"}).status_code == 200


def test_admin_manages_users_and_resets_another_users_password() -> None:
    login_response = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "test-password"})
    headers = {"Authorization": f"Bearer {login_response.json()['data']['access_token']}"}
    created = client.post("/api/v1/admin/users", headers=headers, json={
        "username": "managed-user", "password": "first-password", "role": "operator", "is_active": True,
    })
    assert created.status_code == 201
    managed = created.json()["data"]
    assert any(item["username"] == "managed-user" for item in client.get("/api/v1/admin/users", headers=headers).json()["data"])
    updated = client.put(f"/api/v1/admin/users/{managed['id']}", headers=headers, json={
        "username": "managed-user", "role": "admin", "is_active": True,
    })
    assert updated.status_code == 200
    assert updated.json()["data"]["role"] == "admin"
    reset = client.post(f"/api/v1/admin/users/{managed['id']}/reset-password", headers=headers,
                        json={"new_password": "second-password"})
    assert reset.status_code == 204
    with TestingSession() as db:
        record = db.get(AdminUser, managed["id"])
        assert record is not None and verify_password("second-password", record.password_hash)


def test_user_management_requires_admin_and_protects_current_admin_access() -> None:
    operator_login = client.post("/api/v1/admin/auth/login", json={"username": "operator", "password": "test-password"})
    operator_headers = {"Authorization": f"Bearer {operator_login.json()['data']['access_token']}"}
    assert client.get("/api/v1/admin/users", headers=operator_headers).status_code == 403
    admin_login = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "test-password"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['access_token']}"}
    me = client.get("/api/v1/admin/auth/me", headers=admin_headers).json()["data"]
    denied = client.put(f"/api/v1/admin/users/{me['id']}", headers=admin_headers, json={
        "username": "admin", "role": "operator", "is_active": True,
    })
    assert denied.status_code == 409
    own_reset = client.post(f"/api/v1/admin/users/{me['id']}/reset-password", headers=admin_headers,
                            json={"new_password": "replacement-password"})
    assert own_reset.status_code == 409


def test_bootstrap_credentials_do_not_overwrite_existing_account(monkeypatch) -> None:
    class ExistingAccount:
        password_hash = "changed-password-hash"
        role = "operator"
        is_active = False

    account = ExistingAccount()

    class FakeQuery:
        def filter(self, *_): return self
        def one_or_none(self): return account

    class FakeSession:
        commits = 0
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def query(self, *_): return FakeQuery()
        def commit(self): self.commits += 1

    session = FakeSession()
    monkeypatch.setattr(bootstrap_admin, "SessionLocal", lambda: session)
    monkeypatch.setenv("ADMIN_INITIAL_USERNAME", "bootstrap-once")
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "initial-password")
    bootstrap_admin.main()
    assert account.password_hash == "changed-password-hash"
    assert account.role == "operator" and account.is_active is False
    assert session.commits == 0
