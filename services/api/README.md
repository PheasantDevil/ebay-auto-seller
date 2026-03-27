# Backend API (FastAPI)

Python (FastAPI) service intended to run behind AWS API Gateway (Lambda-style deployment).

## Local development

- Health check: `GET /health`
- Run tests: `pytest`
- Lint/format: `ruff check`, `ruff format`

## Research candidates

- Candidates endpoint: `GET /research/candidates?tenant_id=<uuid>&limit=<int>`
- Requires `DATABASE_URL` to be set (PostgreSQL/Aurora connection string).

## AWS Lambda

`lambda_handler.handler` is the Mangum adapter for FastAPI.

## Expected responsibilities (next steps)

- Read endpoints (research candidates, listings, orders, audit logs)
- Minimal write endpoint for the "one-click" listing creation flow
- Input validation and mapping to domain services

