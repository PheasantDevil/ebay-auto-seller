from decimal import Decimal


def calculate_profit_usd(
    *,
    avg_sold_price_usd: Decimal,
    item_price_usd: Decimal,
    estimated_shipping_usd: Decimal,
    ebay_fee_rate: Decimal,
    sales_tax_rate_assumed: Decimal,
) -> dict[str, Decimal]:
    """Calculate profit components in USD.

    The initial implementation uses assumed rates (e.g., sales tax buffer) and
    computes:
    - eBay fees: avg_sold_price_usd * ebay_fee_rate
    - Sales tax: avg_sold_price_usd * sales_tax_rate_assumed
    - net profit: avg_sold_price_usd - (item_price_usd + shipping + fees + tax)
    """

    ebay_fees_usd = avg_sold_price_usd * ebay_fee_rate
    sales_tax_usd = avg_sold_price_usd * sales_tax_rate_assumed
    net_profit_usd = avg_sold_price_usd - (
        item_price_usd + estimated_shipping_usd + ebay_fees_usd + sales_tax_usd
    )

    return {
        "ebay_fee_usd": ebay_fees_usd,
        "sales_tax_usd": sales_tax_usd,
        "net_profit_usd": net_profit_usd,
    }
