from fastapi.testclient import TestClient

from app.main import app


def test_swagger_and_openapi_include_foundation_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["info"]["version"] == "0.1.0"
    assert "/health" in schema["paths"]
    assert "/api/v1/admin/auth/login" in schema["paths"]
    assert "/api/v1/files/upload" in schema["paths"]
