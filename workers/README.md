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
- `inventory-sync-ebay`: `inventory_current` → `ebay_listings.quantity` + `ebay_listing_updates` (`inventory_sync`)
- `repricing`: `pricing_assumptions` + best sourcing row + latest `market_stats` → `ebay_listings.fixed_price_usd` + `ebay_listing_updates` (`repricing`)
- Stubs: `orders-sync` (next in sequence)

