from decimal import Decimal
from unittest.mock import MagicMock, patch

from orders_sync.fulfillment_client import iter_get_orders
from orders_sync.fulfillment_map import last_modified_filter_since, map_fulfillment_order


def test_last_modified_filter_contains_brackets_and_iso():
    f = last_modified_filter_since(hours_back=24)
    assert f.startswith("lastmodifieddate:[")
    assert f.endswith("..]")
    assert "T" in f


def test_map_fulfillment_order_minimal_usd():
    order = {
        "orderId": "12-34567-89012",
        "creationDate": "2026-01-15T10:00:00.000Z",
        "pricingSummary": {
            "priceSubtotal": {"value": "100.00", "currency": "USD"},
            "deliveryCost": {"value": "5.50", "currency": "USD"},
            "tax": {"value": "8.00", "currency": "USD"},
        },
        "lineItems": [
            {"legacyItemId": "110", "lineItemId": "line-1"},
        ],
        "orderFulfillmentStatus": "FULFILLED",
    }
    row = map_fulfillment_order(order)
    assert row is not None
    assert row.ebay_order_id == "12-34567-89012"
    assert row.sale_price_usd == Decimal("100.00")
    assert row.shipping_paid_usd == Decimal("5.50")
    assert row.tax_paid_usd == Decimal("8.00")
    assert row.ebay_item_id == "110"
    assert row.ebay_transaction_id == "line-1"
    assert row.currency == "USD"
    assert row.return_status == "FULFILLED"
    assert row.raw_payload["orderId"] == "12-34567-89012"


def test_map_fulfillment_order_prefers_usd_conversion():
    order = {
        "orderId": "o-2",
        "creationDate": "2026-02-01T12:00:00.000Z",
        "pricingSummary": {
            "priceSubtotal": {
                "value": "90.00",
                "currency": "EUR",
                "convertedFromValue": "99.50",
                "convertedFromCurrency": "USD",
            },
        },
        "lineItems": [],
    }
    row = map_fulfillment_order(order)
    assert row is not None
    assert row.sale_price_usd == Decimal("99.50")
    assert row.currency == "USD"


def test_map_fulfillment_order_rejects_missing_pricing():
    assert (
        map_fulfillment_order({"orderId": "x", "creationDate": "2026-01-01T00:00:00.000Z"}) is None
    )


def test_iter_get_orders_paginates_until_short_page():
    """Full page (len == limit) then short page => stop (eBay pagination semantics)."""
    page1 = {"orders": [{"orderId": "a"}, {"orderId": "b"}]}
    page2 = {"orders": [{"orderId": "c"}]}

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = [page1, page2]

    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_response

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client_instance
    mock_client_cls.return_value.__exit__.return_value = None

    with patch("orders_sync.fulfillment_client.httpx.Client", mock_client_cls):
        got = iter_get_orders(
            "token",
            filter_expr="lastmodifieddate:[2026-01-01T00:00:00.000Z..]",
            page_limit=2,
            max_orders=10,
        )

    assert len(got) == 3
    assert mock_client_instance.get.call_count == 2
    first_call_kwargs = mock_client_instance.get.call_args_list[0]
    assert "params" in first_call_kwargs.kwargs
    assert first_call_kwargs.kwargs["params"]["offset"] == "0"
    assert first_call_kwargs.kwargs["params"]["limit"] == "2"
    second = mock_client_instance.get.call_args_list[1].kwargs["params"]
    assert second["offset"] == "2"
    assert second["limit"] == "2"
