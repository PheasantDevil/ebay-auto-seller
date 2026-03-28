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
- `sourcing-scan`: event-driven `custom` adapter → `sourcing_item_state_*` + `inventory_current`
- `inventory-sync-ebay`: `inventory_current` → `ebay_listings.quantity` + `ebay_listing_updates` (`inventory_sync`). When `EBAY_INVENTORY_SYNC_ENABLED=true`, calls Sell Inventory `bulk_update_price_quantity` first; set `ebay_listings.policy` JSON with `inventory_item_sku` (or `sku`) and optional `offer_id` / `offerId`. OAuth needs `sell.inventory` scope (included in `common/ebay_oauth.py` default `EBAY_SCOPE` unless overridden). Env: `EBAY_INVENTORY_API_BASE`, `EBAY_MARKETPLACE_ID` (default `EBAY_US`).
- `repricing`: `pricing_assumptions` + best sourcing row + latest `market_stats` → `ebay_listings.fixed_price_usd` + `ebay_listing_updates` (`repricing`)
- `orders-sync`: event `items[]` → `orders` upsert (`tenant_id` + `ebay_order_id`); optional eBay REST ingest later

