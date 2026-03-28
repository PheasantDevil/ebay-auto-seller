import socket
from decimal import Decimal

import pytest

from sourcing_scan.adapters.http_json import (
    is_safe_sourcing_http_url,
    supplier_state_from_http_json,
)


def test_supplier_state_from_http_json_minimal():
    st = supplier_state_from_http_json(
        sourcing_source_item_id="ssi-1",
        variant_id="v-1",
        payload={
            "item_price_usd": "19.99",
            "source_stock_qty": 3,
        },
    )
    assert st is not None
    assert st.item_price_usd == Decimal("19.99")
    assert st.estimated_shipping_usd == Decimal("0")
    assert st.estimated_sales_tax_rate_assumed == Decimal("0.10")
    assert st.source_stock_qty == 3


def test_supplier_state_from_http_json_rejects_missing_price():
    assert (
        supplier_state_from_http_json(
            sourcing_source_item_id="ssi-1",
            variant_id="v-1",
            payload={"source_stock_qty": 1},
        )
        is None
    )


@pytest.fixture
def clear_sourcing_http_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCING_HTTP_ALLOWED_HOSTS", raising=False)


def test_is_safe_rejects_loopback_literal(clear_sourcing_http_allowlist: None) -> None:
    assert not is_safe_sourcing_http_url("http://127.0.0.1/x")


def test_is_safe_accepts_public_literal(clear_sourcing_http_allowlist: None) -> None:
    assert is_safe_sourcing_http_url("http://8.8.8.8/x")


def test_is_safe_rejects_private_literal(clear_sourcing_http_allowlist: None) -> None:
    assert not is_safe_sourcing_http_url("http://10.0.0.1/x")


def test_is_safe_rejects_dns_to_loopback(
    clear_sourcing_http_allowlist: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_gai(*_a: object, **_kw: object) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]

    monkeypatch.setattr("sourcing_scan.adapters.http_json.socket.getaddrinfo", fake_gai)
    assert not is_safe_sourcing_http_url("http://evil.example/x")


def test_allowlist_blocks_unlisted_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_ALLOWED_HOSTS", "partner.example")
    assert not is_safe_sourcing_http_url("http://other.example/x")


def test_allowlist_allows_listed_host_with_global_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCING_HTTP_ALLOWED_HOSTS", "partner.example")

    def fake_gai(*_a: object, **_kw: object) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0))]

    monkeypatch.setattr("sourcing_scan.adapters.http_json.socket.getaddrinfo", fake_gai)
    assert is_safe_sourcing_http_url("http://partner.example/path")


def test_allowlist_still_rejects_private_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_ALLOWED_HOSTS", "partner.example")

    def fake_gai(*_a: object, **_kw: object) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0))]

    monkeypatch.setattr("sourcing_scan.adapters.http_json.socket.getaddrinfo", fake_gai)
    assert not is_safe_sourcing_http_url("http://partner.example/path")


def test_is_safe_without_scheme(clear_sourcing_http_allowlist: None) -> None:
    assert not is_safe_sourcing_http_url("ftp://8.8.8.8/")
