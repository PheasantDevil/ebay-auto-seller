from aws_cdk import Stack
from constructs import Construct


class EbayAutoSellerStack(Stack):
    """
    CDK stack skeleton.

    This is intentionally a placeholder so we can incrementally wire:
    - Aurora Serverless v2 (PostgreSQL)
    - API Gateway -> FastAPI (Lambda)
    - Worker Lambdas (EventBridge schedules)
    - Secrets/config wiring (no secrets in repo)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # TODO: define Aurora + migration/init, then wire API/worker Lambdas.
        # TODO: add Environment variables and Secrets Manager references.
