# =============================================================================
# STACK: Cómputo — Infraestructura de Muestra CGA
# =============================================================================
# ADVERTENCIA: Recursos INTENCIONALMENTE MAL CONFIGURADOS para demo del CGA.
# NO usar como referencia de buenas prácticas.
# =============================================================================

from aws_cdk import (
    Stack,
    Tags,
    CfnOutput,
    Duration,
    aws_ec2 as ec2,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
)
from constructs import Construct


class ComputeStack(Stack):
    """
    Crea recursos de cómputo con problemas intencionales.

    HALLAZGOS ESPERADOS (FinOps):
    - [HIGH]   EC2 't3.large' con CPU histórica ~2% — subutilizada
    - [MEDIUM] EC2 't3.medium' en estado stopped por más de 7 días
    - [LOW]    Lambda 'fn-unused' sin invocaciones en 30+ días
    - [LOW]    Lambda 'fn-legacy' sin invocaciones en 30+ días

    HALLAZGOS ESPERADOS (Security):
    - [MEDIUM] Lambda 'fn-unused' sin log group en CloudWatch

    HALLAZGOS ESPERADOS (Compliance):
    - [MEDIUM] EC2 'ec2-no-tags' sin tags Owner, Project, Environment, CostCenter
    - [MEDIUM] Lambda 'fn-legacy' sin tag CostCenter
    """

    def __init__(self, scope: Construct, construct_id: str,
                 vpc: ec2.Vpc, sg_web: ec2.SecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # AMI Amazon Linux 2023 (última versión)
        # ---------------------------------------------------------------
        amzn_linux = ec2.MachineImage.latest_amazon_linux2023()

        # ---------------------------------------------------------------
        # EC2 #1 — Instancia sobredimensionada, CPU ~2% (FinOps: HIGH)
        # Simula un servidor de aplicación que quedó encendido sin uso real
        # ---------------------------------------------------------------
        ec2_oversized = ec2.Instance(
            self,
            "Ec2Oversized",
            instance_type=ec2.InstanceType("t3.large"),
            machine_image=amzn_linux,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_group=sg_web,
            instance_name="ec2-oversized-backend",
            # Sin key pair — no hay acceso SSH (al menos eso)
            # Pero el SG de red lo tiene abierto (detectado por network_stack)
        )

        Tags.of(ec2_oversized).add("Name",        "ec2-oversized-backend")
        Tags.of(ec2_oversized).add("Owner",       "backend@acme-corp.com")
        Tags.of(ec2_oversized).add("Project",     "plataforma-legacy")
        Tags.of(ec2_oversized).add("Environment", "production")
        Tags.of(ec2_oversized).add("CostCenter",  "ENG-002")
        Tags.of(ec2_oversized).add("Note",        "Subutilizada - CPU promedio 2pct - hallazgo CGA")

        # ---------------------------------------------------------------
        # EC2 #2 — Instancia DETENIDA hace más de 7 días (FinOps: MEDIUM)
        # Simula un servidor de staging que nadie terminó de eliminar
        # ---------------------------------------------------------------
        ec2_stopped = ec2.Instance(
            self,
            "Ec2Stopped",
            instance_type=ec2.InstanceType("t3.medium"),
            machine_image=amzn_linux,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_group=sg_web,
            instance_name="ec2-stopped-staging",
        )

        Tags.of(ec2_stopped).add("Name",        "ec2-stopped-staging")
        Tags.of(ec2_stopped).add("Owner",       "devops@acme-corp.com")
        Tags.of(ec2_stopped).add("Project",     "plataforma-staging")
        Tags.of(ec2_stopped).add("Environment", "staging")
        Tags.of(ec2_stopped).add("CostCenter",  "ENG-001")
        Tags.of(ec2_stopped).add("Note",        "Detenida hace 15 dias - hallazgo CGA")

        # ---------------------------------------------------------------
        # EC2 #3 — SIN TAGS obligatorios (Compliance: MEDIUM x4)
        # Simula un recurso creado manualmente sin seguir el estándar
        # ---------------------------------------------------------------
        ec2_no_tags = ec2.Instance(
            self,
            "Ec2NoTags",
            instance_type=ec2.InstanceType("t3.small"),
            machine_image=amzn_linux,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg_web,
            instance_name="ec2-no-tags",
        )
        # Sin tags Owner, Project, Environment, CostCenter — 4 hallazgos de compliance

        # ---------------------------------------------------------------
        # Lambda #1 — Sin invocaciones en 30+ días (FinOps: LOW)
        #             Sin log group configurado (Security: MEDIUM)
        # Simula una función legacy que nadie recuerda para qué sirve
        # ---------------------------------------------------------------
        fn_unused = _lambda.Function(
            self,
            "FnUnused",
            function_name="fn-unused-processor",
            runtime=_lambda.Runtime.PYTHON_3_9,   # Runtime desactualizado
            handler="index.handler",
            code=_lambda.Code.from_inline("""
def handler(event, context):
    # Función legacy sin uso — hallazgo CGA
    print("Esta función no se ha invocado en 30+ días")
    return {"statusCode": 200}
"""),
            timeout=Duration.seconds(30),
            memory_size=128,
            # Sin log group explícito — Lambda crea uno automáticamente,
            # pero sin configurar retención (detectado por logging_checker)
        )

        Tags.of(fn_unused).add("Name",        "fn-unused-processor")
        Tags.of(fn_unused).add("Owner",       "backend@acme-corp.com")
        Tags.of(fn_unused).add("Project",     "plataforma-legacy")
        Tags.of(fn_unused).add("Environment", "production")
        Tags.of(fn_unused).add("CostCenter",  "ENG-002")
        Tags.of(fn_unused).add("Note",        "Sin invocaciones 30 dias - hallazgo CGA")

        # ---------------------------------------------------------------
        # Lambda #2 — Sin invocaciones, sin CostCenter (FinOps + Compliance)
        # Simula un webhook que se dejó de usar tras migración
        # ---------------------------------------------------------------
        fn_legacy = _lambda.Function(
            self,
            "FnLegacy",
            function_name="fn-legacy-webhook",
            runtime=_lambda.Runtime.PYTHON_3_8,   # Runtime EOL
            handler="index.handler",
            code=_lambda.Code.from_inline("""
def handler(event, context):
    # Webhook legacy sin uso tras migración a EventBridge
    return {"statusCode": 200, "body": "legacy"}
"""),
            timeout=Duration.seconds(60),
            memory_size=256,
        )

        Tags.of(fn_legacy).add("Name",        "fn-legacy-webhook")
        Tags.of(fn_legacy).add("Owner",       "integrations@acme-corp.com")
        Tags.of(fn_legacy).add("Project",     "integraciones")
        Tags.of(fn_legacy).add("Environment", "production")
        # CostCenter ausente intencionalmente — hallazgo compliance

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "Ec2OversizedId", value=ec2_oversized.instance_id, export_name="SampleEc2OversizedId")
        CfnOutput(self, "Ec2StoppedId",   value=ec2_stopped.instance_id,   export_name="SampleEc2StoppedId")
        CfnOutput(self, "FnUnusedArn",    value=fn_unused.function_arn,    export_name="SampleFnUnusedArn")
        CfnOutput(self, "FnLegacyArn",    value=fn_legacy.function_arn,    export_name="SampleFnLegacyArn")
