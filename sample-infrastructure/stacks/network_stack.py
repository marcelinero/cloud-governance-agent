# =============================================================================
# STACK: Red y Perímetro — Infraestructura de Muestra CGA
# =============================================================================
# ADVERTENCIA: Este stack crea recursos INTENCIONALMENTE MAL CONFIGURADOS
# para ser detectados por el Cloud Governance Agent (CGA).
# NO usar como referencia de buenas prácticas. Solo para demostración.
# =============================================================================

from aws_cdk import (
    Stack,
    Tags,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    CfnOutput,
    Duration,
)
from constructs import Construct


class NetworkStack(Stack):
    """
    Crea la infraestructura de red de muestra con problemas intencionales:

    HALLAZGOS ESPERADOS (Security):
    - [CRITICAL] Security Group 'web-open-sg' con SSH (22) abierto a 0.0.0.0/0
    - [CRITICAL] Security Group 'db-open-sg' con MySQL (3306) abierto a 0.0.0.0/0
    - [CRITICAL] Security Group 'db-open-sg' con PostgreSQL (5432) abierto a 0.0.0.0/0
    - [CRITICAL] Security Group 'db-open-sg' con RDP (3389) abierto a 0.0.0.0/0
    - [MEDIUM]   VPC sin Flow Logs activos

    HALLAZGOS ESPERADOS (FinOps):
    - [HIGH]     ALB 'alb-idle' sin tráfico en los últimos 7 días
    - [LOW]      Elastic IP no asociada a ningún recurso
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # VPC — SIN Flow Logs (hallazgo intencional: MEDIUM security)
        # ---------------------------------------------------------------
        self.vpc = ec2.Vpc(
            self,
            "SampleVpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            # NAT Gateway eliminado (nat_gateways=0) para evitar costo fijo (~$32/mes).
            # Free-tier friendly: solo subredes públicas e isoladas.
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
            # Flow logs DESHABILITADOS intencionalmente — hallazgo CGA
            flow_logs={},
        )

        # Tags incompletos — falta CostCenter (hallazgo de cumplimiento)
        Tags.of(self.vpc).add("Name", "sample-production-vpc")
        Tags.of(self.vpc).add("Owner", "infra@acme-corp.com")
        Tags.of(self.vpc).add("Project", "plataforma-core")
        Tags.of(self.vpc).add("Environment", "production")
        # CostCenter ausente intencionalmente

        # ---------------------------------------------------------------
        # Security Group WEB — Puerto SSH 22 abierto al mundo (CRITICAL)
        # ---------------------------------------------------------------
        self.sg_web = ec2.SecurityGroup(
            self,
            "SgWebOpen",
            vpc=self.vpc,
            security_group_name="web-open-sg",
            description="SG para servidores web - INSEGURO (demo CGA)",
            allow_all_outbound=True,
        )

        # HTTP y HTTPS (aceptables)
        self.sg_web.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80),  "HTTP")
        self.sg_web.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # SSH abierto al mundo — CRÍTICO, detectado por CGA
        self.sg_web.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            "SSH abierto al mundo - INSEGURO",
        )

        Tags.of(self.sg_web).add("Name", "web-open-sg")
        Tags.of(self.sg_web).add("Owner", "devops@acme-corp.com")
        Tags.of(self.sg_web).add("Project", "plataforma-core")
        Tags.of(self.sg_web).add("Environment", "production")
        Tags.of(self.sg_web).add("CostCenter", "ENG-001")

        # ---------------------------------------------------------------
        # Security Group DB — Puertos de BD + RDP abiertos al mundo (CRITICAL)
        # ---------------------------------------------------------------
        self.sg_db = ec2.SecurityGroup(
            self,
            "SgDbOpen",
            vpc=self.vpc,
            security_group_name="db-open-sg",
            description="SG para bases de datos - INSEGURO (demo CGA)",
            allow_all_outbound=True,
        )

        # MySQL abierto al mundo — CRÍTICO
        self.sg_db.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(3306),
            "MySQL abierto al mundo - INSEGURO",
        )
        # PostgreSQL abierto al mundo — CRÍTICO
        self.sg_db.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(5432),
            "PostgreSQL abierto al mundo - INSEGURO",
        )
        # RDP abierto al mundo — CRÍTICO
        self.sg_db.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(3389),
            "RDP abierto al mundo - INSEGURO",
        )
        # MS SQL abierto al mundo — CRÍTICO
        self.sg_db.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(1433),
            "MSSQL abierto al mundo - INSEGURO",
        )

        Tags.of(self.sg_db).add("Name", "db-open-sg")
        Tags.of(self.sg_db).add("Owner", "dba@acme-corp.com")
        Tags.of(self.sg_db).add("Project", "plataforma-core")
        Tags.of(self.sg_db).add("Environment", "production")
        Tags.of(self.sg_db).add("CostCenter", "ENG-001")

        # ---------------------------------------------------------------
        # Elastic IP — No asociada a ningún recurso (hallazgo FinOps: LOW)
        # ---------------------------------------------------------------
        self.eip_orphan = ec2.CfnEIP(
            self,
            "OrphanEIP",
            tags=[
                {"key": "Name",        "value": "eip-orphan-demo"},
                {"key": "Owner",       "value": "devops@acme-corp.com"},
                {"key": "Project",     "value": "plataforma-core"},
                {"key": "Environment", "value": "production"},
                {"key": "CostCenter",  "value": "ENG-001"},
                {"key": "Note",        "value": "EIP huerfana - hallazgo CGA intencional"},
            ],
        )
        # No se asocia a ninguna instancia — genera hallazgo FinOps

        # ---------------------------------------------------------------
        # ALB — Creado pero sin target groups con instancias sanas
        # Simula un Load Balancer abandonado (hallazgo FinOps: HIGH)
        # ---------------------------------------------------------------
        self.alb_idle = elbv2.ApplicationLoadBalancer(
            self,
            "AlbIdle",
            vpc=self.vpc,
            internet_facing=True,
            load_balancer_name="alb-idle-demo",
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # Listener sin targets registrados — genera 0 requests
        idle_target_group = elbv2.ApplicationTargetGroup(
            self,
            "IdleTargetGroup",
            vpc=self.vpc,
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                path="/health",
                interval=Duration.seconds(30),
            ),
        )

        self.alb_idle.add_listener(
            "IdleListener",
            port=80,
            default_target_groups=[idle_target_group],
        )

        Tags.of(self.alb_idle).add("Name", "alb-idle-demo")
        Tags.of(self.alb_idle).add("Owner", "devops@acme-corp.com")
        Tags.of(self.alb_idle).add("Project", "plataforma-legacy")
        Tags.of(self.alb_idle).add("Environment", "production")
        Tags.of(self.alb_idle).add("CostCenter", "ENG-002")

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "VpcId",          value=self.vpc.vpc_id,        export_name="SampleVpcId")
        CfnOutput(self, "SgWebId",        value=self.sg_web.security_group_id, export_name="SampleSgWebId")
        CfnOutput(self, "SgDbId",         value=self.sg_db.security_group_id,  export_name="SampleSgDbId")
        CfnOutput(self, "AlbIdleDns",     value=self.alb_idle.load_balancer_dns_name, export_name="SampleAlbIdleDns")
