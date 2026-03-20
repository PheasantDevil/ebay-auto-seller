# Backend API (FastAPI)

Python (FastAPI) service intended to run behind AWS API Gateway (Lambda-style deployment).

## Local development

- Health check: `GET /health`
- Run tests: `pytest`
- Lint/format: `ruff check`, `ruff format`

## AWS Lambda

`lambda_handler.handler` is the Mangum adapter for FastAPI.

# Backend API (FastAPI)

Python (FastAPI) service intended to run behind AWS API Gateway (Lambda-style deployment).

Expected responsibilities:
- Read endpoints (research candidates, listings, orders, audit logs)
- Minimal write endpoint for the "one-click" listing creation flow
- Input validation and mapping to domain services

Initial scaffold will be added in a later work item.

