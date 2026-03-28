# Workers (AWS Lambda)

Serverless worker functions for scheduled and event-driven jobs.

Planned Lambdas:
- `market-stats-refresh`: refresh eBay Sold Listings stats
- `sourcing-scan`: fetch price/stock snapshots from supplier EC sites
- `inventory-sync-ebay`: set eBay quantity to 0 when supplier stock is 0
- `repricing`: update fixed price on eBay based on profit simulation rules
- `orders-sync`: import sales/orders and finalize profit reporting

Current state:
- `market-stats-refresh`: OAuth + Browse API proxy → `market_stats` + `job_runs`
- `sourcing-scan`: loads active `sourcing_source_items` + `sourcing_sources`; rows rotate by `last_fetched_at` (oldest first) and the column is updated after each HTTP fetch attempt. `http_json` GETs `source_url` (absolute https) with the JSON contract below. `amazon` / `walmart` / `target` use the same JSON over HTTPS: either set `source_url` on the row, or set env `AMAZON_SOURCING_JSON_URL_TEMPLATE` / `WALMART_SOURCING_JSON_URL_TEMPLATE` / `TARGET_SOURCING_JSON_URL_TEMPLATE` (placeholders `{product_id}` or `{external_product_id}`) and fill `external_product_id` on the row (tenant proxy / partner API). SSRF: globally routable IPs; optional `SOURCING_HTTP_ALLOWED_HOSTS`. Event `items[]` (`custom`) overrides same `sourcing_source_item_id`. JSON: `item_price_usd`, `source_stock_qty`, optional `estimated_shipping_usd`, `estimated_sales_tax_rate_assumed`. Env: `SOURCING_HTTP_TIMEOUT_SEC`, `SOURCING_HTTP_USER_AGENT`, `SOURCING_HTTP_ALLOWED_HOSTS`.
- `inventory-sync-ebay`: `inventory_current` → `ebay_listings.quantity` + `ebay_listing_updates` (`inventory_sync`). When `EBAY_INVENTORY_SYNC_ENABLED=true`, calls Sell Inventory `bulk_update_price_quantity` first; set `ebay_listings.policy` JSON with `inventory_item_sku` (or `sku`) and optional `offer_id` / `offerId`. OAuth needs `sell.inventory` scope (included in `common/ebay_oauth.py` default `EBAY_SCOPE` unless overridden). Env: `EBAY_INVENTORY_API_BASE`, `EBAY_MARKETPLACE_ID` (default `EBAY_US`).
- `repricing`: `pricing_assumptions` + best sourcing row + latest `market_stats` → `ebay_listings.fixed_price_usd` + `ebay_listing_updates` (`repricing`)
- `orders-sync`: event `items[]` → `orders` upsert (`tenant_id` + `ebay_order_id`). Or `source: "ebay_fulfillment"` + tenant eBay OAuth: Sell Fulfillment `getOrders` with `lastmodifieddate` filter (hours from `hours_back` or env `ORDERS_EBAY_SYNC_HOURS_BACK`, default 720; use `hours_back: 0` for eBay default unfiltered window). Env: `EBAY_FULFILLMENT_API_BASE`, `EBAY_MARKETPLACE_ID`, `ORDERS_EBAY_PAGE_LIMIT`. Default OAuth scope includes `sell.fulfillment.readonly` (re-consent if tokens predate this).

