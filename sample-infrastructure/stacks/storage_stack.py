# =============================================================================
# STACK: Almacenamiento — Infraestructura de Muestra CGA
# =============================================================================
# ADVERTENCIA: Recursos INTENCIONALMENTE MAL CONFIGURADOS para demo del CGA.
# NO usar como referencia de buenas prácticas.
# =============================================================================

from aws_cdk import (
    Stack,
    Tags,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ec2 as ec2,
)
from constructs import Construct


class StorageStack(Stack):
    """
    Crea recursos de almacenamiento con problemas intencionales.

    HALLAZGOS ESPERADOS (Security):
    - [CRITICAL] S3 'bucket-public-demo' con acceso público habilitado
    - [MEDIUM]   S3 'bucket-public-demo' sin server access logging
    - [MEDIUM]   S3 'bucket-nologs-demo' sin server access logging

    HALLAZGOS ESPERADOS (FinOps):
    - [MEDIUM]   S3 'bucket-nologs-demo' sin lifecycle policy
    - [MEDIUM]   S3 'bucket-public-demo' sin lifecycle policy
    - [MEDIUM]   Volumen EBS 'vol-orphan' en estado available +7 días
    - [LOW]      S3 'bucket-archive-demo' con objetos en Standard sin lifecycle a Glacier

    HALLAZGOS ESPERADOS (Compliance):
    - [MEDIUM]   S3 'bucket-public-demo' sin tags Owner, Project, Environment, CostCenter
    - [MEDIUM]   S3 'bucket-nologs-demo' sin tag CostCenter
    """

    def __init__(self, scope: Construct, construct_id: str,
                 vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # S3 #1 — Bucket con acceso público HABILITADO (Security: CRITICAL)
        # Sin logging, sin lifecycle, sin tags correctos
        # Simula un bucket de assets estáticos mal configurado
        # ---------------------------------------------------------------
        bucket_public = s3.Bucket(
            self,
            "BucketPublic",
            bucket_name=None,  # nombre generado automáticamente
            # Acceso público habilitado — CRÍTICO
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            public_read_access=True,
            versioning_enabled=False,
            encryption=s3.BucketEncryption.UNENCRYPTED,  # Sin cifrado
            enforce_ssl=False,                            # Sin HTTPS obligatorio
            removal_policy=RemovalPolicy.DESTROY,
        )
        # Sin tags obligatorios — 4 hallazgos de compliance
        Tags.of(bucket_public).add("Note", "bucket-publico-demo-hallazgo-CGA")

        # ---------------------------------------------------------------
        # S3 #2 — Bucket sin lifecycle policy (FinOps: MEDIUM)
        #         Sin server access logging (Security: MEDIUM)
        # Simula un bucket de logs de aplicación que fue creciendo sin control
        # ---------------------------------------------------------------
        bucket_nologs = s3.Bucket(
            self,
            "BucketNoLogs",
            versioning_enabled=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            # Sin lifecycle policy — objetos acumulados indefinidamente
            # Sin server_access_logs_bucket — hallazgo security
        )

        Tags.of(bucket_nologs).add("Name",        "bucket-applogs-demo")
        Tags.of(bucket_nologs).add("Owner",       "devops@acme-corp.com")
        Tags.of(bucket_nologs).add("Project",     "plataforma-core")
        Tags.of(bucket_nologs).add("Environment", "production")
        # CostCenter ausente intencionalmente

        # ---------------------------------------------------------------
        # S3 #3 — Bucket de archivo sin transición a Glacier (FinOps: LOW)
        # Simula datos históricos que podrían moverse a almacenamiento barato
        # ---------------------------------------------------------------
        bucket_archive = s3.Bucket(
            self,
            "BucketArchive",
            versioning_enabled=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            # Sin lifecycle hacia Glacier — objetos en Standard siendo costosos
        )

        Tags.of(bucket_archive).add("Name",        "bucket-archive-demo")
        Tags.of(bucket_archive).add("Owner",       "dataeng@acme-corp.com")
        Tags.of(bucket_archive).add("Project",     "data-platform")
        Tags.of(bucket_archive).add("Environment", "production")
        Tags.of(bucket_archive).add("CostCenter",  "DATA-001")
        Tags.of(bucket_archive).add("Note",        "Sin lifecycle a Glacier - hallazgo CGA FinOps")

        # ---------------------------------------------------------------
        # S3 #4 — Bucket de logs (bien configurado, sirve como referencia)
        # Este bucket es el destino de server access logs de otros buckets
        # ---------------------------------------------------------------
        bucket_logs = s3.Bucket(
            self,
            "BucketAccessLogs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-logs-90d",
                    expiration=__import__("aws_cdk").Duration.days(90),
                    enabled=True,
                )
            ],
            removal_policy=RemovalPolicy.DESTROY,
        )

        Tags.of(bucket_logs).add("Name",        "bucket-access-logs")
        Tags.of(bucket_logs).add("Owner",       "security@acme-corp.com")
        Tags.of(bucket_logs).add("Project",     "plataforma-core")
        Tags.of(bucket_logs).add("Environment", "production")
        Tags.of(bucket_logs).add("CostCenter",  "SEC-001")

        # ---------------------------------------------------------------
        # Volumen EBS huérfano — en estado 'available' sin instancia (FinOps: MEDIUM)
        # Simula un disco de datos que quedó suelto tras terminar una instancia
        # ---------------------------------------------------------------
        ebs_orphan = ec2.CfnVolume(
            self,
            "EbsOrphan",
            availability_zone=f"{self.region}a",
            size=100,          # 100 GB pagando sin uso
            volume_type="gp3",
            encrypted=False,   # Sin cifrado — también es un hallazgo de seguridad
            tags=[
                {"key": "Name",        "value": "vol-orphan-data"},
                {"key": "Owner",       "value": "devops@acme-corp.com"},
                {"key": "Project",     "value": "plataforma-legacy"},
                {"key": "Environment", "value": "production"},
                {"key": "CostCenter",  "value": "ENG-002"},
                {"key": "Note",        "value": "Volumen huerfano - no adjunto a ninguna instancia - hallazgo CGA"},
            ],
        )
        # No se adjunta a ninguna instancia — permanece en estado 'available'

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "BucketPublicName",  value=bucket_public.bucket_name,  export_name="SampleBucketPublicName")
        CfnOutput(self, "BucketNoLogsName",  value=bucket_nologs.bucket_name,  export_name="SampleBucketNoLogsName")
        CfnOutput(self, "BucketArchiveName", value=bucket_archive.bucket_name, export_name="SampleBucketArchiveName")
        CfnOutput(self, "EbsOrphanId",       value=ebs_orphan.ref,             export_name="SampleEbsOrphanId")
