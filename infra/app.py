#!/usr/bin/env python3

import os

from aws_cdk import App
from aws_cdk import Environment

from stack import EbayAutoSellerStack

app = App()

account = os.environ.get("CDK_DEFAULT_ACCOUNT")
region = os.environ.get("CDK_DEFAULT_REGION")
env = Environment(account=account, region=region) if account and region else None

EbayAutoSellerStack(app, "EbayAutoSellerStack", env=env)
app.synth()
