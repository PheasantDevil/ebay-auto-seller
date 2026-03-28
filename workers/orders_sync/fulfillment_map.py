"""Map eBay Fulfillment Order JSON to OrderUpsertRow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from orders_sync.logic import compute_net_profit_usd_baseline
from orders_sync.repository import OrderUpsertRow


def map_fulfillment_order(order: dict[str, Any]) -> OrderUpsertRow | None:
    """Best-effort mapping; full order kept in raw_payload."""
    ebay_order_id = order.get("orderId")
    creation = order.get("creationDate")
    if not ebay_order_id or not creation:
        return None

    sold_at = _parse_iso_datetime(str(creation))
    ps = order.get("pricingSummary")
    if not isinstance(ps, dict):
        return None

    price_subtotal = ps.get("priceSubtotal")
    total = ps.get("total")
    primary_amount = price_subtotal if isinstance(price_subtotal, dict) else total
    if not isinstance(primary_amount, dict):
        return None

    sale_dec, currency = _amount_to_decimal_and_currency(primary_amount)
    ship_dec, _ = _optional_amount(ps.get("deliveryCost"))
    tax_dec, _ = _optional_amount(ps.get("tax"))

    line_items = order.get("lineItems")
    ebay_item_id: str | None = None
    ebay_transaction_id: str | None = None
    if isinstance(line_items, list) and line_items:
        first = line_items[0]
        if isinstance(first, dict):
            legacy = first.get("legacyItemId")
            if legacy is not None:
                ebay_item_id = str(legacy)
            liid = first.get("lineItemId")
            if liid is not None:
                ebay_transaction_id = str(liid)

    fulfillment = order.get("orderFulfillmentStatus")
    return_status = str(fulfillment) if fulfillment is not None else None

    net_profit = compute_net_profit_usd_baseline(
        sale_price_usd=sale_dec,
        ebay_fees_usd=None,
        cogs_usd=None,
        tax_paid_usd=tax_dec,
    )

    return OrderUpsertRow(
        ebay_order_id=str(ebay_order_id),
        ebay_transaction_id=ebay_transaction_id,
        ebay_listing_id=None,
        ebay_item_id=ebay_item_id,
        variant_id=None,
        sold_at=sold_at,
        sale_price_usd=sale_dec.quantize(Decimal("0.01")),
        shipping_paid_usd=None if ship_dec is None else ship_dec.quantize(Decimal("0.01")),
        tax_paid_usd=None if tax_dec is None else tax_dec.quantize(Decimal("0.01")),
        ebay_fees_usd=None,
        cogs_usd=None,
        net_profit_usd=net_profit,
        currency=currency,
        return_status=return_status,
        raw_payload=dict(order),
    )


def last_modified_filter_since(*, hours_back: int) -> str:
    """eBay filter for orders modified on or after (now - hours_back)."""
    since = datetime.now(UTC) - timedelta(hours=max(1, int(hours_back)))
    iso = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return f"lastmodifieddate:[{iso}..]"


def _parse_iso_datetime(value: str) -> datetime:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _amount_to_decimal_and_currency(amount: dict[str, Any]) -> tuple[Decimal, str]:
    """Prefer USD from conversion fields when marketplace reports non-USD."""
    cur = str(amount.get("currency") or "USD").upper()[:3]
    if len(cur) < 3:
        cur = "USD"
    val = amount.get("value")
    if val is None:
        raise ValueError("amount missing value")
    if cur == "USD":
        return Decimal(str(val)), cur
    conv_cur = amount.get("convertedFromCurrency")
    conv_val = amount.get("convertedFromValue")
    if conv_cur and str(conv_cur).upper()[:3] == "USD" and conv_val is not None:
        return Decimal(str(conv_val)), "USD"
    return Decimal(str(val)), cur


def _optional_amount(obj: object) -> tuple[Decimal | None, str | None]:
    if not isinstance(obj, dict):
        return None, None
    try:
        d, c = _amount_to_decimal_and_currency(obj)
        return d, c
    except ValueError, TypeError, KeyError:
        return None, None
