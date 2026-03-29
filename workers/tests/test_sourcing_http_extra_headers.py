import json

import pytest

from sourcing_scan.adapters import http_json


def test_extra_headers_json_merged_into_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SOURCING_HTTP_EXTRA_HEADERS_JSON",
        json.dumps({"X-Api-Key": "k1", "Authorization": "Bearer tok"}),
    )
    monkeypatch.setenv("SOURCING_HTTP_USER_AGENT", "ua-test")

    captured: dict[str, object] = {}

    class FakeResp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"item_price_usd": "9.99", "source_stock_qty": 2}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def get(self, url: str, headers: dict | None = None) -> FakeResp:
            captured["url"] = url
            captured["headers"] = dict(headers or {})
            return FakeResp()

    monkeypatch.setattr(http_json.httpx, "Client", FakeClient)
    monkeypatch.setattr(http_json, "is_safe_sourcing_http_url", lambda _u: True)

    st = http_json.fetch_supplier_state_from_get_url(
        url="https://public.example/item.json",
        sourcing_source_item_id="ssi",
        variant_id="v1",
    )
    assert st is not None
    h = captured["headers"]
    assert h.get("User-Agent") == "ua-test"
    assert h.get("X-Api-Key") == "k1"
    assert h.get("Authorization") == "Bearer tok"


def test_extra_headers_invalid_json_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_EXTRA_HEADERS_JSON", "not-json")
    assert http_json._extra_headers_from_env() == {}


def test_extra_headers_non_object_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCING_HTTP_EXTRA_HEADERS_JSON", "[1,2]")
    assert http_json._extra_headers_from_env() == {}
