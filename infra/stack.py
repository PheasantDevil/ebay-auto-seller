import os

from aws_cdk import BundlingOptions, CfnOutput, DockerImage, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class EbayAutoSellerStack(Stack):
    """VPC, Aurora Serverless v2, API (Lambda + HTTP API), and scheduled workers."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sam_python = DockerImage.from_registry(
            "public.ecr.aws/sam/build-python3.11:latest",
        )

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="PrivateEgress",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        db_admin_secret = secretsmanager.Secret(
            self,
            "AuroraAdminSecret",
            description="Admin credentials for ebay-auto-seller Aurora PostgreSQL",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username":"dbadmin"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=24,
            ),
        )

        db_security_group = ec2.SecurityGroup(
            self,
            "AuroraSecurityGroup",
            vpc=vpc,
            description="Security group for Aurora PostgreSQL cluster",
            allow_all_outbound=True,
        )

        cluster = rds.ServerlessCluster(
            self,
            "AuroraCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_4,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                one_per_az=True,
            ),
            security_groups=[db_security_group],
            default_database_name="ebayautoseller",
            credentials=rds.Credentials.from_secret(
                db_admin_secret,
                username="dbadmin",
            ),
            scaling=rds.ServerlessScalingOptions(
                min_capacity=rds.AuroraCapacityUnit.ACU_1,
                max_capacity=rds.AuroraCapacityUnit.ACU_4,
                auto_pause=Duration.minutes(10),
            ),
            removal_policy=RemovalPolicy.DESTROY,
            backup_retention=Duration.days(7),
        )

        lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=vpc,
            description="Outbound from API and worker Lambdas",
            allow_all_outbound=True,
        )

        db_security_group.add_ingress_rule(
            peer=lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL from Lambda security group",
        )

        aurora_env = {
            "AURORA_SECRET_ARN": db_admin_secret.secret_arn,
            "PGHOST": cluster.cluster_endpoint.hostname,
            "PGPORT": "5432",
            "PGDATABASE": "ebayautoseller",
        }

        api_lambda = lambda_.Function(
            self,
            "ApiLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_handler.handler",
            code=lambda_.Code.from_asset(
                "../services/api",
                exclude=["tests", ".pytest_cache", "__pycache__", "*.pyc", ".ruff_cache"],
                bundling=BundlingOptions(
                    image=sam_python,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements-lambda.txt -t /asset-output && "
                        "cp -r app /asset-output/ && cp lambda_handler.py /asset-output/",
                    ],
                ),
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_security_group],
            timeout=Duration.seconds(30),
            memory_size=512,
            environment=aurora_env,
            log_retention=logs.RetentionDays.THREE_DAYS,
        )
        db_admin_secret.grant_read(api_lambda)

        http_integration = apigwv2_integrations.HttpLambdaIntegration(
            "ApiHttpIntegration",
            api_lambda,
        )
        http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            default_integration=http_integration,
        )

        orders_lambda = lambda_.Function(
            self,
            "OrdersSyncLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="orders_sync.handler.handler",
            code=lambda_.Code.from_asset(
                "../workers",
                exclude=[
                    "tests",
                    ".pytest_cache",
                    "__pycache__",
                    "*.pyc",
                    ".ruff_cache",
                ],
                bundling=BundlingOptions(
                    image=sam_python,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements-lambda-orders.txt -t /asset-output && "
                        "cp -r orders_sync common /asset-output/",
                    ],
                ),
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_security_group],
            timeout=Duration.seconds(120),
            memory_size=512,
            environment=aurora_env,
            log_retention=logs.RetentionDays.THREE_DAYS,
        )
        db_admin_secret.grant_read(orders_lambda)

        orders_tenant = os.environ.get("ORDERS_SYNC_DEFAULT_TENANT_ID", "").strip()
        if orders_tenant:
            events.Rule(
                self,
                "OrdersSyncSchedule",
                schedule=events.Schedule.rate(Duration.minutes(30)),
                targets=[
                    events_targets.LambdaFunction(
                        orders_lambda,
                        event=events.RuleTargetInput.from_object(
                            {"tenant_id": orders_tenant},
                        ),
                    ),
                ],
            )

        CfnOutput(
            self,
            "AuroraClusterEndpoint",
            value=cluster.cluster_endpoint.hostname,
            export_name="EbayAutoSellerAuroraEndpoint",
        )
        CfnOutput(
            self,
            "AuroraAdminSecretArn",
            value=db_admin_secret.secret_arn,
            export_name="EbayAutoSellerAuroraAdminSecretArn",
        )
        CfnOutput(
            self,
            "HttpApiUrl",
            value=http_api.api_endpoint,
            export_name="EbayAutoSellerHttpApiUrl",
        )
