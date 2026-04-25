import pytest

from sourcing_scan.adapters.url_signing import (
    apply_sourcing_url_hmac,
    is_sourcing_url_signing_enabled,
)


def test_signing_disabled_by_default() -> None:
    assert apply_sourcing_url_hmac("https://x.example/a") == "https://x.example/a"


def test_signing_disabled_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_ENABLED", "true")
    monkeypatch.delenv("SOURCING_HTTP_SIGNING_SECRET", raising=False)
    assert apply_sourcing_url_hmac("https://x.example/a") == "https://x.example/a"


def test_signing_appends_ts_and_sig(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_ENABLED", "true")
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_SECRET", "hunter2")
    out = apply_sourcing_url_hmac("https://x.example/path", now_ts=1700000000)
    assert "sourcing_ts=1700000000" in out
    assert "sourcing_sig=" in out
    assert out.startswith("https://x.example/path?")


def test_signing_preserves_existing_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_ENABLED", "true")
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_SECRET", "secret")
    out = apply_sourcing_url_hmac(
        "https://x.example/p?foo=1&bar=two",
        now_ts=100,
    )
    assert "foo=1" in out
    assert "bar=two" in out
    assert "sourcing_ts=100" in out


def test_signing_stable_for_same_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_ENABLED", "true")
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_SECRET", "k")
    a = apply_sourcing_url_hmac("https://h.example/z?q=1", now_ts=5)
    b = apply_sourcing_url_hmac("https://h.example/z?q=1", now_ts=5)
    assert a == b


def test_is_sourcing_url_signing_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCING_HTTP_SIGNING_ENABLED", raising=False)
    assert is_sourcing_url_signing_enabled() is False
    monkeypatch.setenv("SOURCING_HTTP_SIGNING_ENABLED", "true")
    assert is_sourcing_url_signing_enabled() is True
