# =============================================================================
# STACK: Base de Datos — Infraestructura de Muestra CGA
# =============================================================================
# ADVERTENCIA: Recursos INTENCIONALMENTE MAL CONFIGURADOS para demo del CGA.
# NO usar como referencia de buenas prácticas.
# =============================================================================

from aws_cdk import (
    Stack,
    Tags,
    CfnOutput,
    RemovalPolicy,
    Duration,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class DatabaseStack(Stack):
    """
    Crea recursos de base de datos con problemas intencionales.

    HALLAZGOS ESPERADOS (Security):
    - [HIGH]   RDS 'rds-public-mysql' con PubliclyAccessible = True
    - [HIGH]   RDS 'rds-public-mysql' sin Multi-AZ en entorno production
    - [MEDIUM] RDS 'rds-stopped-pg' sin Multi-AZ

    HALLAZGOS ESPERADOS (FinOps):
    - [HIGH]   RDS 'rds-stopped-pg' en estado stopped por más de 7 días
    - [HIGH]   RDS 'rds-public-mysql' con CPU < 10% en 7 días
    - [LOW]    DynamoDB 'tbl-inactive' con < 10 ops/día en 7 días

    HALLAZGOS ESPERADOS (Compliance):
    - [MEDIUM] RDS 'rds-public-mysql' sin tag CostCenter
    - [MEDIUM] DynamoDB 'tbl-inactive' sin tags Owner, Project, Environment
    """

    def __init__(self, scope: Construct, construct_id: str,
                 vpc: ec2.Vpc, sg_db: ec2.SecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # RDS #1 — MySQL con acceso público habilitado (Security: HIGH)
        # CPU < 10%, sin Multi-AZ, sin CostCenter
        # Simula una base de datos de desarrollo expuesta en producción
        # ---------------------------------------------------------------
        rds_public = rds.DatabaseInstance(
            self,
            "RdsPublicMysql",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            # Free-tier: db.t3.micro (750h/mes gratis). El hallazgo de acceso
            # público no depende del tamaño de la instancia.
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC  # En subnet pública — INSEGURO
            ),
            security_groups=[sg_db],
            # Acceso público habilitado — hallazgo CRÍTICO
            publicly_accessible=True,
            # Sin Multi-AZ — hallazgo en producción
            multi_az=False,
            allocated_storage=20,
            max_allocated_storage=100,
            database_name="appdb",
            credentials=rds.Credentials.from_generated_secret("admin"),
            backup_retention=Duration.days(1),   # Retención mínima
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            # Sin Performance Insights — dificulta detectar bajo uso
            enable_performance_insights=False,
            # Sin Enhanced Monitoring
            monitoring_interval=Duration.seconds(0),
        )

        Tags.of(rds_public).add("Name",        "rds-public-mysql")
        Tags.of(rds_public).add("Owner",       "dba@acme-corp.com")
        Tags.of(rds_public).add("Project",     "plataforma-core")
        Tags.of(rds_public).add("Environment", "production")
        # CostCenter ausente intencionalmente — hallazgo compliance
        Tags.of(rds_public).add("Note",        "RDS publico - CPU baja - hallazgo CGA")

        # ---------------------------------------------------------------
        # RDS #2 — PostgreSQL DETENIDA (FinOps: HIGH)
        # Simula una base de datos de reportes que nadie usa
        # Nota: CDK crea la instancia; se detiene manualmente post-deploy
        #       El custom resource automatiza el stop inicial
        # ---------------------------------------------------------------
        rds_stopped = rds.DatabaseInstance(
            self,
            "RdsStoppedPostgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_7
            ),
            # Free-tier: db.t3.micro. El hallazgo de sin Multi-AZ no depende del tamaño.
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[sg_db],
            publicly_accessible=False,
            multi_az=False,           # Sin Multi-AZ — hallazgo security
            allocated_storage=20,
            database_name="reportsdb",
            credentials=rds.Credentials.from_generated_secret("pgadmin"),
            backup_retention=Duration.days(7),
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
        )

        Tags.of(rds_stopped).add("Name",        "rds-stopped-postgres")
        Tags.of(rds_stopped).add("Owner",       "dataeng@acme-corp.com")
        Tags.of(rds_stopped).add("Project",     "data-platform")
        Tags.of(rds_stopped).add("Environment", "production")
        Tags.of(rds_stopped).add("CostCenter",  "DATA-001")
        Tags.of(rds_stopped).add("Note",        "RDS detenida 15 dias - hallazgo CGA FinOps")

        # ---------------------------------------------------------------
        # DynamoDB — Tabla inactiva (FinOps: LOW)
        # Sin tags de Owner/Project/Environment (Compliance: MEDIUM)
        # Simula una tabla de sesiones de usuario de una app descontinuada
        # ---------------------------------------------------------------
        tbl_inactive = dynamodb.Table(
            self,
            "TblInactive",
            table_name="tbl-inactive-sessions",
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING,
            ),
            # Modo PROVISIONED sobredimensionado — sin uso real
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=10,
            write_capacity=10,
            removal_policy=RemovalPolicy.DESTROY,
            # Sin Point-in-time recovery
            point_in_time_recovery=False,
        )

        # Sin tags Owner, Project, Environment — 3 hallazgos de compliance
        Tags.of(tbl_inactive).add("CostCenter", "ENG-001")
        Tags.of(tbl_inactive).add("Note",       "Tabla inactiva - sin ops en 7 dias - hallazgo CGA")

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "RdsPublicEndpoint",
                  value=rds_public.db_instance_endpoint_address,
                  export_name="SampleRdsPublicEndpoint")
        CfnOutput(self, "RdsStoppedEndpoint",
                  value=rds_stopped.db_instance_endpoint_address,
                  export_name="SampleRdsStoppedEndpoint")
        CfnOutput(self, "DynamoTableName",
                  value=tbl_inactive.table_name,
                  export_name="SampleDynamoTableName")
