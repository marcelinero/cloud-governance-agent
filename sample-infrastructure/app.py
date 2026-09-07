#!/usr/bin/env python3
# =============================================================================
# app.py — Entry point CDK para Infraestructura de Muestra CGA
# =============================================================================
# Despliega una compañía ficticia "ACME Corp" simulando producción con
# recursos intencionalmente mal configurados para ser detectados por el CGA.
#
# ORDEN DE DESPLIEGUE (dependencias entre stacks):
#   1. NetworkStack      — VPC, SGs, EIP, ALB
#   2. StorageStack      — S3 buckets, EBS huérfano (depende de VPC)
#   3. ComputeStack      — EC2, Lambda (depende de VPC + SGs)
#   4. DatabaseStack     — RDS, DynamoDB (depende de VPC + SGs)
#   5. IamStack          — Usuarios IAM (sin dependencias de red)
#   6. FrontendStack     — CloudFront (sin dependencias de VPC)
#
# USO:
#   cd sample-infrastructure
#   pip install -r requirements.txt
#   cdk bootstrap
#   cdk deploy --all
#
# COSTO ESTIMADO: ~$15-25 USD/día con todos los recursos activos.
# Recordar ejecutar `cdk destroy --all` al terminar la demo.
# =============================================================================

import aws_cdk as cdk
from stacks.network_stack  import NetworkStack
from stacks.storage_stack  import StorageStack
from stacks.compute_stack  import ComputeStack
from stacks.database_stack import DatabaseStack
from stacks.iam_stack      import IamStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

# Leer configuración del contexto (cdk.json)
account = app.node.try_get_context("account")
region  = app.node.try_get_context("region") or "us-east-1"
env     = cdk.Environment(account=account, region=region)

# ---------------------------------------------------------------
# Stack 1: Red y Perímetro
# ---------------------------------------------------------------
network = NetworkStack(
    app,
    "CGA-Sample-Network",
    env=env,
    description="[CGA Demo] Red: VPC, Security Groups inseguros, EIP huerfana, ALB inactivo",
)

# ---------------------------------------------------------------
# Stack 2: Almacenamiento
# ---------------------------------------------------------------
storage = StorageStack(
    app,
    "CGA-Sample-Storage",
    vpc=network.vpc,
    env=env,
    description="[CGA Demo] Storage: S3 publico, sin lifecycle, EBS huerfano",
)
storage.add_dependency(network)

# ---------------------------------------------------------------
# Stack 3: Cómputo
# ---------------------------------------------------------------
compute = ComputeStack(
    app,
    "CGA-Sample-Compute",
    vpc=network.vpc,
    sg_web=network.sg_web,
    env=env,
    description="[CGA Demo] Compute: EC2 subutilizada/detenida, Lambda sin invocaciones",
)
compute.add_dependency(network)

# ---------------------------------------------------------------
# Stack 4: Base de Datos
# ---------------------------------------------------------------
database = DatabaseStack(
    app,
    "CGA-Sample-Database",
    vpc=network.vpc,
    sg_db=network.sg_db,
    env=env,
    description="[CGA Demo] Database: RDS publica/detenida, DynamoDB inactiva",
)
database.add_dependency(network)

# ---------------------------------------------------------------
# Stack 5: IAM
# ---------------------------------------------------------------
iam_stack = IamStack(
    app,
    "CGA-Sample-IAM",
    env=env,
    description="[CGA Demo] IAM: usuarios sin MFA, keys antiguas, politicas permisivas",
)

# ---------------------------------------------------------------
# Stack 6: Frontend
# ---------------------------------------------------------------
frontend = FrontendStack(
    app,
    "CGA-Sample-Frontend",
    env=env,
    description="[CGA Demo] Frontend: CloudFront sin WAF, HTTP permitido",
)

# Tags globales aplicados a todos los stacks
cdk.Tags.of(app).add("ManagedBy",   "CDK")
cdk.Tags.of(app).add("Project",     "CGA-Sample-Infrastructure")
cdk.Tags.of(app).add("Purpose",     "Cloud Governance Agent Demo")
cdk.Tags.of(app).add("Repository",  "cloud-governance-agent")

app.synth()
