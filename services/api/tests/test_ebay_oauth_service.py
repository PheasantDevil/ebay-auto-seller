from app.services.ebay_oauth import build_ebay_auth_url


def test_build_ebay_auth_url(monkeypatch) -> None:
    """Ensure auth URL includes required query parameters."""
    monkeypatch.setenv("EBAY_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_REDIRECT_URI", "redirect-uri")
    monkeypatch.setenv("EBAY_SCOPE", "scope-a scope-b")
    monkeypatch.setenv("EBAY_OAUTH_BASE_URL", "https://example.com/authorize")

    url = build_ebay_auth_url(tenant_id="tenant-1")

    assert url.startswith("https://example.com/authorize?")
    assert "client_id=client-id" in url
    assert "response_type=code" in url
    assert "redirect_uri=redirect-uri" in url
    assert "state=tenant-1" in url
