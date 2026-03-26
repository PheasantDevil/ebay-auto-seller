from fastapi.testclient import TestClient

from app.main import app


def test_start_ebay_auth_returns_authorization_url(monkeypatch) -> None:
    """Ensure `/auth/ebay/start` builds and returns OAuth URL."""
    monkeypatch.setenv("EBAY_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_REDIRECT_URI", "redirect-uri")
    monkeypatch.setenv("EBAY_SCOPE", "scope-a scope-b")
    monkeypatch.setenv("EBAY_OAUTH_BASE_URL", "https://example.com/authorize")

    client = TestClient(app)
    resp = client.get("/auth/ebay/start", params={"tenant_id": "tenant-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert "authorization_url" in body
    assert body["authorization_url"].startswith("https://example.com/authorize?")
