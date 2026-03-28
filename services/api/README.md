# Backend API (FastAPI)

Python (FastAPI) service intended to run behind AWS API Gateway (Lambda-style deployment).

## Local development

- Health check: `GET /health`
- Run tests: `pytest`
- Lint/format: `ruff check`, `ruff format`

## eBay OAuth endpoints

- `GET /auth/ebay/start?tenant_id=<uuid>`: returns eBay consent URL.
- `GET /auth/ebay/callback?tenant_id=<uuid>&code=<authorization_code>`: exchanges code and stores encrypted tokens.
- Required env vars:
  - `EBAY_CLIENT_ID`
  - `EBAY_CLIENT_SECRET`
  - `EBAY_REDIRECT_URI`
  - `EBAY_TOKEN_ENCRYPTION_KEY`
  - `DATABASE_URL`
  - Default app scope includes `sell.fulfillment.readonly` (see workers `common/ebay_oauth.py`); sellers must re-authorize if tokens were issued before that scope was added.

## AWS Lambda

`lambda_handler.handler` is the Mangum adapter for FastAPI.

## Expected responsibilities (next steps)

- Read endpoints (research candidates, listings, orders, audit logs)
- Minimal write endpoint for the "one-click" listing creation flow
- Input validation and mapping to domain services

