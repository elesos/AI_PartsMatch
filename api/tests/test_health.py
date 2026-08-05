from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"status": "healthy"}}


def test_version_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == "0.1.0"
