"""
network_checker.py — Auditoría FinOps de recursos de red AWS.

Checks implementados:
  - [LOW]  Elastic IPs no asociadas a ningún recurso
  - [HIGH] NAT Gateways sin tráfico en los últimos 7 días
  - [HIGH] Load Balancers (ALB/NLB) sin tráfico en los últimos 7 días
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

# Costos de red (us-east-1)
EIP_COST_PER_HOUR    = 0.005     # ~$3.65/mes
NAT_BASE_COST_MONTH  = 32.85     # $0.045/hora × 730h
ALB_BASE_COST_MONTH  = 18.40     # $0.008/hora × 730h (sin LCU)
NLB_BASE_COST_MONTH  = 18.40


class NetworkFinOpsChecker(BaseChecker):
    """Detecta recursos de red ociosos que generan costo sin utilidad."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.ec2 = factory.get_client("ec2")
        self.elb = factory.get_client("elbv2")
        self.cw  = factory.get_client("cloudwatch")
        self.lookback_days = 7

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando NetworkFinOpsChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            findings.extend(self._check_orphan_eips())
            findings.extend(self._check_idle_nat_gateways())
            findings.extend(self._check_idle_load_balancers())
        except Exception as e:
            self.logger.error("Error en NetworkFinOpsChecker", extra={"error": str(e)})

        self.logger.info("NetworkFinOpsChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # Check 1: Elastic IPs huérfanas
    # ------------------------------------------------------------------
    def _check_orphan_eips(self) -> List[Finding]:
        findings = []
        try:
            resp = self.ec2.describe_addresses()
            for addr in resp.get("Addresses", []):
                # EIP no asociada si no tiene InstanceId ni NetworkInterfaceId
                if addr.get("InstanceId") or addr.get("NetworkInterfaceId"):
                    continue

                eip_id    = addr.get("AllocationId", addr.get("PublicIp", "unknown"))
                public_ip = addr.get("PublicIp", "unknown")
                tags      = self._extract_tags(addr.get("Tags", []))
                monthly   = round(EIP_COST_PER_HOUR * 730, 2)

                findings.append(
                    self._build_finding(
                        domain="finops",
                        category="network",
                        severity="low",
                        resource_id=eip_id,
                        resource_type="AWS::EC2::EIP",
                        title=f"Elastic IP no asociada: {public_ip}",
                        description=(
                            f"La Elastic IP '{public_ip}' ({eip_id}) no está asociada "
                            f"a ninguna instancia ni interfaz de red. AWS cobra por EIPs "
                            f"no utilizadas: ~${monthly:.2f} USD/mes."
                        ),
                        recommendation=(
                            f"Si la IP no es necesaria, liberarla: EC2 → Elastic IPs → "
                            f"{public_ip} → Actions → Release Elastic IP address."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        estimated_monthly_cost=monthly,
                        potential_saving=monthly,
                        evidence={
                            "allocation_id":   eip_id,
                            "public_ip":       public_ip,
                            "association_id":  addr.get("AssociationId"),
                            "domain":          addr.get("Domain"),
                        },
                    )
                )
        except Exception as e:
            self.logger.error("Error verificando EIPs", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 2: NAT Gateways sin tráfico
    # ------------------------------------------------------------------
    def _check_idle_nat_gateways(self) -> List[Finding]:
        findings = []
        try:
            paginator = self.ec2.get_paginator("describe_nat_gateways")
            for page in paginator.paginate(
                Filters=[{"Name": "state", "Values": ["available"]}]
            ):
                for nat in page.get("NatGateways", []):
                    nat_id    = nat["NatGatewayId"]
                    vpc_id    = nat.get("VpcId", "unknown")
                    subnet_id = nat.get("SubnetId", "unknown")
                    tags      = self._extract_tags(nat.get("Tags", []))
                    name      = self._get_tag(tags, "name") or nat_id

                    bytes_out = self._get_nat_traffic(nat_id)
                    if bytes_out is not None and bytes_out == 0:
                        findings.append(
                            self._build_finding(
                                domain="finops",
                                category="network",
                                severity="high",
                                resource_id=nat_id,
                                resource_type="AWS::EC2::NatGateway",
                                title=f"NAT Gateway sin tráfico {self.lookback_days} días: {name}",
                                description=(
                                    f"El NAT Gateway '{name}' ({nat_id}) en la VPC "
                                    f"'{vpc_id}' no ha procesado tráfico en los últimos "
                                    f"{self.lookback_days} días. "
                                    f"Costo mensual fijo: ~${NAT_BASE_COST_MONTH:.2f} USD "
                                    f"(sin contar costo por GB procesado)."
                                ),
                                recommendation=(
                                    f"Verificar si hay recursos en la subred privada que "
                                    f"necesitan el NAT Gateway. Si no hay tráfico legítimo, "
                                    f"eliminar el NAT Gateway '{nat_id}' para ahorrar "
                                    f"~${NAT_BASE_COST_MONTH:.2f} USD/mes."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                estimated_monthly_cost=NAT_BASE_COST_MONTH,
                                potential_saving=NAT_BASE_COST_MONTH,
                                evidence={
                                    "nat_gateway_id": nat_id,
                                    "vpc_id":         vpc_id,
                                    "subnet_id":      subnet_id,
                                    "bytes_out_7d":   0,
                                },
                            )
                        )
        except Exception as e:
            self.logger.error("Error verificando NAT Gateways", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 3: Load Balancers sin tráfico
    # ------------------------------------------------------------------
    def _check_idle_load_balancers(self) -> List[Finding]:
        findings = []
        try:
            paginator = self.elb.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancers", []):
                    lb_arn    = lb["LoadBalancerArn"]
                    lb_name   = lb["LoadBalancerName"]
                    lb_type   = lb.get("Type", "application").lower()
                    lb_scheme = lb.get("Scheme", "internet-facing")
                    tags      = self._get_elb_tags(lb_arn)

                    requests = self._get_lb_requests(lb_arn, lb_name, lb_type)
                    if requests is not None and requests == 0:
                        base_cost = ALB_BASE_COST_MONTH if lb_type == "application" else NLB_BASE_COST_MONTH

                        findings.append(
                            self._build_finding(
                                domain="finops",
                                category="network",
                                severity="high",
                                resource_id=lb_arn,
                                resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
                                title=f"{lb_type.upper()} sin tráfico {self.lookback_days} días: {lb_name}",
                                description=(
                                    f"El Load Balancer '{lb_name}' ({lb_type.upper()}, {lb_scheme}) "
                                    f"no ha procesado requests en los últimos {self.lookback_days} días. "
                                    f"Costo mensual fijo: ~${base_cost:.2f} USD/mes."
                                ),
                                recommendation=(
                                    f"Verificar si el LB '{lb_name}' está recibiendo tráfico real. "
                                    f"Si está abandonado, eliminar el Load Balancer y sus listeners "
                                    f"para ahorrar ~${base_cost:.2f} USD/mes."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                estimated_monthly_cost=base_cost,
                                potential_saving=base_cost,
                                evidence={
                                    "lb_arn":       lb_arn,
                                    "lb_name":      lb_name,
                                    "lb_type":      lb_type,
                                    "lb_scheme":    lb_scheme,
                                    "requests_7d":  0,
                                },
                            )
                        )
        except Exception as e:
            self.logger.error("Error verificando Load Balancers", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Helpers de métricas
    # ------------------------------------------------------------------
    def _get_nat_traffic(self, nat_id: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/NATGateway",
            MetricName="BytesOutToDestination",
            Dimensions=[{"Name": "NatGatewayId", "Value": nat_id}],
            StartTime=start, EndTime=end,
            Period=self.lookback_days * 86400,
            Statistics=["Sum"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0
        return sum(d["Sum"] for d in datapoints)

    def _get_lb_requests(
        self, lb_arn: str, lb_name: str, lb_type: str
    ) -> Optional[float]:
        end    = datetime.now(timezone.utc)
        start  = end - timedelta(days=self.lookback_days)
        metric = "RequestCount" if lb_type == "application" else "ActiveFlowCount"
        dim_key = "LoadBalancer"
        # Extraer la parte corta del ARN para la dimensión
        dim_val = "/".join(lb_arn.split(":")[-1].split("/")[1:])

        resp = self.cw.get_metric_statistics(
            Namespace="AWS/ApplicationELB" if lb_type == "application" else "AWS/NetworkELB",
            MetricName=metric,
            Dimensions=[{"Name": dim_key, "Value": dim_val}],
            StartTime=start, EndTime=end,
            Period=self.lookback_days * 86400,
            Statistics=["Sum"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0
        return sum(d["Sum"] for d in datapoints)

    def _get_elb_tags(self, lb_arn: str) -> Dict[str, str]:
        try:
            resp = self.elb.describe_tags(ResourceArns=[lb_arn])
            tag_descs = resp.get("TagDescriptions", [])
            if tag_descs:
                return self._extract_tags(tag_descs[0].get("Tags", []))
        except Exception:
            pass
        return {}
