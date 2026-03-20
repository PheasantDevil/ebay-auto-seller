# Infrastructure (IaC)

AWS Infrastructure as Code for:
- Lambda + API Gateway
- Scheduled jobs (EventBridge)
- Aurora Serverless v2 provisioning
- Secrets & configuration wiring

## Current state

This repo currently contains an AWS CDK (Python) skeleton (not yet fully wired).

Planned next steps:
- Aurora Serverless v2 (PostgreSQL) cluster + init schema/migrations
- FastAPI API Gateway + auth wiring
- Lambda functions for each worker job + EventBridge schedules
- Build/deploy wiring for frontend (Amplify/CloudFront) in a later item


