from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
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
        """Initialize the CDK stack (VPC + Aurora Serverless v2)."""
        super().__init__(scope, construct_id, **kwargs)

        # VPC: 2 AZ, single NAT Gateway (low cost), public + private-with-egress subnets.
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

        # Secrets Manager: generated credentials for Aurora admin user.
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

        # Aurora Serverless v2 (PostgreSQL) cluster.
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
            engine=rds.DatabaseClusterEngine.AURORA_POSTGRESQL,
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
            # Low-cost starting point; can be tuned later based on load.
            scaling=rds.ServerlessScalingOptions(
                min_capacity=rds.AuroraCapacityUnit.ACU_0_5,
                max_capacity=rds.AuroraCapacityUnit.ACU_4,
                auto_pause=Duration.minutes(10),
            ),
            removal_policy=RemovalPolicy.DESTROY,
            backup_retention=Duration.days(7),
        )

        # Allow incoming connections from within the VPC (Lambdas will use this later).
        db_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL from VPC",
        )

        # Useful outputs for wiring API/workers and for manual checks.
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
