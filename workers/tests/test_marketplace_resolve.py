import pytest

from sourcing_scan.adapters.marketplace_resolve import resolve_marketplace_json_url
from sourcing_scan.repository import SourcingDbItem


def _row(
    *,
    source_url: str = "",
    external_product_id: str | None = None,
) -> SourcingDbItem:
    return SourcingDbItem(
        sourcing_source_item_id="ssi-1",
        variant_id="v-1",
        source_type="amazon",
        source_url=source_url,
        external_product_id=external_product_id,
    )


def test_resolve_prefers_absolute_source_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AMAZON_SOURCING_JSON_URL_TEMPLATE", "https://wrong.example/{product_id}")
    url = resolve_marketplace_json_url(
        _row(source_url="https://right.example/p.json"),
        template_env="AMAZON_SOURCING_JSON_URL_TEMPLATE",
    )
    assert url == "https://right.example/p.json"


def test_resolve_template_with_product_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "WALMART_SOURCING_JSON_URL_TEMPLATE",
        "https://proxy.example/walmart/{product_id}",
    )
    url = resolve_marketplace_json_url(
        _row(external_product_id="SKU-9"),
        template_env="WALMART_SOURCING_JSON_URL_TEMPLATE",
    )
    assert url == "https://proxy.example/walmart/SKU-9"


def test_resolve_template_external_product_id_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "TARGET_SOURCING_JSON_URL_TEMPLATE",
        "https://proxy.example/t/{external_product_id}",
    )
    url = resolve_marketplace_json_url(
        _row(external_product_id="T-1"),
        template_env="TARGET_SOURCING_JSON_URL_TEMPLATE",
    )
    assert url == "https://proxy.example/t/T-1"


def test_resolve_none_without_template_and_relative_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AMAZON_SOURCING_JSON_URL_TEMPLATE", raising=False)
    assert (
        resolve_marketplace_json_url(
            _row(source_url="", external_product_id="X"),
            template_env="AMAZON_SOURCING_JSON_URL_TEMPLATE",
        )
        is None
    )


def test_resolve_none_template_without_external_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AMAZON_SOURCING_JSON_URL_TEMPLATE", "https://x/{product_id}")
    assert (
        resolve_marketplace_json_url(
            _row(source_url=""),
            template_env="AMAZON_SOURCING_JSON_URL_TEMPLATE",
        )
        is None
    )
