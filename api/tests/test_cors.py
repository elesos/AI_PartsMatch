from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.cors import DatabaseCORSMiddleware


def cors_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        DatabaseCORSMiddleware, "_allowed_origins",
        staticmethod(lambda: {"https://match.elesos.cc", "https://match-admin.elesos.cc"}),
    )
    app = FastAPI()

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(DatabaseCORSMiddleware)
    return TestClient(app)


def test_allowed_preflight_is_empty_and_credentialed(monkeypatch) -> None:
    response = cors_client(monkeypatch).options("/probe", headers={
        "Origin": "https://match.elesos.cc",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["access-control-allow-origin"] == "https://match.elesos.cc"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]
    assert response.headers["vary"] == "Origin"


def test_unknown_origin_preflight_is_rejected_without_cors_headers(monkeypatch) -> None:
    response = cors_client(monkeypatch).options("/probe", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_allowed_actual_request_receives_exact_origin(monkeypatch) -> None:
    response = cors_client(monkeypatch).get("/probe", headers={"Origin": "https://match-admin.elesos.cc"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://match-admin.elesos.cc"
    assert response.headers["access-control-allow-credentials"] == "true"
