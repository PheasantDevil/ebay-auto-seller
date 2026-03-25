from fastapi.testclient import TestClient

from app.main import app


def test_health():
    """Ensure the health endpoint is reachable and returns the expected payload."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
