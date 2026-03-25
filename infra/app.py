#!/usr/bin/env python3

from aws_cdk import App

from stack import EbayAutoSellerStack

app = App()
EbayAutoSellerStack(app, "EbayAutoSellerStack")
app.synth()
