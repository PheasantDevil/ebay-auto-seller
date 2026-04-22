import os

from aws_cdk import BundlingOptions, CfnOutput, DockerImage, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
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
        worker_common_env = {
            **aurora_env,
            "EBAY_TOKEN_ENCRYPTION_KEY": os.environ.get("EBAY_TOKEN_ENCRYPTION_KEY", ""),
            "EBAY_CLIENT_ID": os.environ.get("EBAY_CLIENT_ID", ""),
            "EBAY_CLIENT_SECRET": os.environ.get("EBAY_CLIENT_SECRET", ""),
            "EBAY_SCOPE": os.environ.get("EBAY_SCOPE", ""),
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
            environment=worker_common_env,
            log_retention=logs.RetentionDays.THREE_DAYS,
        )

        inventory_lambda = self._create_worker_lambda(
            "InventorySyncEbayLambda",
            "inventory_sync_ebay.handler.handler",
            sam_python=sam_python,
            vpc=vpc,
            lambda_security_group=lambda_security_group,
            environment=worker_common_env,
            timeout_seconds=120,
        )
        repricing_lambda = self._create_worker_lambda(
            "RepricingLambda",
            "repricing.handler.handler",
            sam_python=sam_python,
            vpc=vpc,
            lambda_security_group=lambda_security_group,
            environment=worker_common_env,
            timeout_seconds=120,
        )
        sourcing_lambda = self._create_worker_lambda(
            "SourcingScanLambda",
            "sourcing_scan.handler.handler",
            sam_python=sam_python,
            vpc=vpc,
            lambda_security_group=lambda_security_group,
            environment=worker_common_env,
            timeout_seconds=180,
        )
        market_stats_lambda = self._create_worker_lambda(
            "MarketStatsRefreshLambda",
            "market_stats_refresh.handler.handler",
            sam_python=sam_python,
            vpc=vpc,
            lambda_security_group=lambda_security_group,
            environment=worker_common_env,
            timeout_seconds=180,
        )

        for fn in (
            orders_lambda,
            inventory_lambda,
            repricing_lambda,
            sourcing_lambda,
            market_stats_lambda,
        ):
            db_admin_secret.grant_read(fn)

        self._create_schedule_rule(
            "OrdersSyncSchedule",
            target_lambda=orders_lambda,
            tenant_env_name="ORDERS_SYNC_DEFAULT_TENANT_ID",
            default_minutes=30,
        )
        self._create_schedule_rule(
            "InventorySyncSchedule",
            target_lambda=inventory_lambda,
            tenant_env_name="INVENTORY_SYNC_DEFAULT_TENANT_ID",
            default_minutes=5,
        )
        self._create_schedule_rule(
            "RepricingSchedule",
            target_lambda=repricing_lambda,
            tenant_env_name="REPRICING_DEFAULT_TENANT_ID",
            default_minutes=30,
        )
        self._create_schedule_rule(
            "SourcingScanSchedule",
            target_lambda=sourcing_lambda,
            tenant_env_name="SOURCING_SCAN_DEFAULT_TENANT_ID",
            default_minutes=5,
        )
        self._create_schedule_rule(
            "MarketStatsRefreshSchedule",
            target_lambda=market_stats_lambda,
            tenant_env_name="MARKET_STATS_DEFAULT_TENANT_ID",
            default_minutes=60,
            event_payload={"tenant_id": "__TENANT__", "variant_limit": 20},
        )

        alarms_topic = sns.Topic(
            self,
            "RuntimeAlarmsTopic",
            display_name="ebay-auto-seller runtime alarms",
        )
        alert_email = os.environ.get("ALERT_EMAIL", "").strip()
        if alert_email:
            alarms_topic.add_subscription(sns_subscriptions.EmailSubscription(alert_email))

        for logical_name, fn in (
            ("ApiLambdaErrors", api_lambda),
            ("OrdersSyncLambdaErrors", orders_lambda),
            ("InventorySyncLambdaErrors", inventory_lambda),
            ("RepricingLambdaErrors", repricing_lambda),
            ("SourcingScanLambdaErrors", sourcing_lambda),
            ("MarketStatsLambdaErrors", market_stats_lambda),
        ):
            cloudwatch.Alarm(
                self,
                logical_name,
                metric=fn.metric_errors(period=Duration.minutes(5)),
                threshold=1,
                evaluation_periods=1,
                alarm_description=f"{fn.function_name} has runtime errors",
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            ).add_alarm_action(
                cloudwatch_actions.SnsAction(alarms_topic),
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
        CfnOutput(
            self,
            "RuntimeAlarmsTopicArn",
            value=alarms_topic.topic_arn,
            export_name="EbayAutoSellerRuntimeAlarmsTopicArn",
        )

    def _create_worker_lambda(
        self,
        logical_id: str,
        handler: str,
        *,
        sam_python: DockerImage,
        vpc: ec2.IVpc,
        lambda_security_group: ec2.ISecurityGroup,
        environment: dict[str, str],
        timeout_seconds: int,
    ) -> lambda_.Function:
        return lambda_.Function(
            self,
            logical_id,
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler=handler,
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
                        "cp -r orders_sync inventory_sync_ebay repricing sourcing_scan "
                        "market_stats_refresh common /asset-output/",
                    ],
                ),
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_security_group],
            timeout=Duration.seconds(timeout_seconds),
            memory_size=512,
            environment=environment,
            log_retention=logs.RetentionDays.THREE_DAYS,
        )

    def _create_schedule_rule(
        self,
        logical_id: str,
        *,
        target_lambda: lambda_.IFunction,
        tenant_env_name: str,
        default_minutes: int,
        event_payload: dict[str, object] | None = None,
    ) -> None:
        tenant_id = (
            os.environ.get(tenant_env_name, "").strip()
            or os.environ.get("WORKER_DEFAULT_TENANT_ID", "").strip()
        )
        if not tenant_id:
            return

        schedule_minutes = int(
            os.environ.get(f"{tenant_env_name}_SCHEDULE_MINUTES", str(default_minutes)),
        )
        payload: dict[str, object] = {"tenant_id": tenant_id}
        if event_payload:
            payload = {
                key: (tenant_id if value == "__TENANT__" else value)
                for key, value in event_payload.items()
            }

        events.Rule(
            self,
            logical_id,
            schedule=events.Schedule.rate(Duration.minutes(schedule_minutes)),
            targets=[
                events_targets.LambdaFunction(
                    target_lambda,
                    event=events.RuleTargetInput.from_object(payload),
                ),
            ],
        )
