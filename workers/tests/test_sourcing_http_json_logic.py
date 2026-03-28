from decimal import Decimal

from sourcing_scan.adapters.http_json import supplier_state_from_http_json


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
