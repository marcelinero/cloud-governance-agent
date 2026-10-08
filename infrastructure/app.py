#!/usr/bin/env python3
"""
Entry point CDK — Cloud Governance Agent (CGA)
Despliega el agente de auditoría en la cuenta AWS configurada.
"""

import aws_cdk as cdk
from stacks.cga_stack import CGAStack

app = cdk.App()

account = app.node.try_get_context("account")
region  = app.node.try_get_context("region") or "us-east-1"

stack = CGAStack(
    app,
    "CloudGovernanceAgent",
    env=cdk.Environment(account=account, region=region),
    description="Cloud Governance Agent — Auditoría continua, seguridad y FinOps para AWS",
)

# Tags obligatorios — se propagan a TODOS los recursos del stack
cdk.Tags.of(stack).add("Project",    "CGA")
cdk.Tags.of(stack).add("Env",        "PDN")
cdk.Tags.of(stack).add("Owner",      "CloudOps")
cdk.Tags.of(stack).add("CostCenter", "CGA-PDN")
cdk.Tags.of(stack).add("ManagedBy",  "CDK")
cdk.Tags.of(stack).add("Repository", "github.com/marcelinero/cloud-governance-agent")

app.synth()
