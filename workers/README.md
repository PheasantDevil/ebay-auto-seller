# Workers (AWS Lambda)

Serverless worker functions for scheduled and event-driven jobs.

Planned Lambdas:
- `market-stats-refresh`: refresh eBay Sold Listings stats
- `sourcing-scan`: fetch price/stock snapshots from supplier EC sites
- `inventory-sync-ebay`: set eBay quantity to 0 when supplier stock is 0
- `repricing`: update fixed price on eBay based on profit simulation rules
- `orders-sync`: import sales/orders and finalize profit reporting

Current state:
- Worker handler stubs are implemented under `workers/*/handler.py`.
- `market-stats-refresh` now has a baseline implementation:
  - reads encrypted OAuth token from DB
  - refreshes token when needed
  - queries eBay Browse API (listing-price proxy)
  - writes `market_stats` and `job_runs`

