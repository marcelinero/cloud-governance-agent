"""
network_checker.py — Auditoría de seguridad de red en AWS.

Checks implementados:
  - [CRITICAL] Security Groups con puertos críticos abiertos a 0.0.0.0/0
               (SSH:22, RDP:3389, MySQL:3306, PostgreSQL:5432, MSSQL:1433, MongoDB:27017)
  - [MEDIUM]   VPCs sin Flow Logs activos
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

# Puertos críticos que no deben estar abiertos al mundo
CRITICAL_PORTS: List[Tuple[int, str]] = [
    (22,    "SSH"),
    (3389,  "RDP"),
    (3306,  "MySQL"),
    (5432,  "PostgreSQL"),
    (1433,  "MSSQL"),
    (27017, "MongoDB"),
    (6379,  "Redis"),
    (9200,  "Elasticsearch"),
]

OPEN_CIDRS = {"0.0.0.0/0", "::/0"}


class NetworkChecker(BaseChecker):
    """Audita configuraciones de seguridad de red: Security Groups y VPC Flow Logs."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.ec2 = factory.get_client("ec2")

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de seguridad de red."""
        self.logger.info("Iniciando NetworkChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []

        try:
            findings.extend(self._check_security_groups())
            findings.extend(self._check_vpc_flow_logs())
        except Exception as e:
            self.logger.error("Error en NetworkChecker", extra={"error": str(e)})

        self.logger.info(
            "NetworkChecker completado",
            extra={"findings": len(findings)},
        )
        return findings

    # ------------------------------------------------------------------
    # Check 1: Security Groups con puertos críticos abiertos
    # ------------------------------------------------------------------
    def _check_security_groups(self) -> List[Finding]:
        findings = []
        paginator = self.ec2.get_paginator("describe_security_groups")

        for page in paginator.paginate():
            for sg in page.get("SecurityGroups", []):
                sg_id   = sg["GroupId"]
                sg_name = sg.get("GroupName", sg_id)
                vpc_id  = sg.get("VpcId", "unknown")
                tags    = self._extract_tags(sg.get("Tags", []))

                for rule in sg.get("IpPermissions", []):
                    from_port = rule.get("FromPort", 0)
                    to_port   = rule.get("ToPort",   65535)
                    protocol  = rule.get("IpProtocol", "-1")

                    # Protocolo -1 = todo el tráfico
                    if protocol == "-1":
                        open_cidrs = (
                            [r["CidrIp"]   for r in rule.get("IpRanges",   []) if r.get("CidrIp")   in OPEN_CIDRS] +
                            [r["CidrIpv6"] for r in rule.get("Ipv6Ranges", []) if r.get("CidrIpv6") in OPEN_CIDRS]
                        )
                        if open_cidrs:
                            findings.append(self._sg_finding(
                                sg_id, sg_name, vpc_id, tags,
                                port="All", service="Todo el tráfico",
                                cidr=open_cidrs[0], severity="critical",
                                from_port=0, to_port=65535,
                            ))
                        continue

                    for port, service in CRITICAL_PORTS:
                        if not (from_port <= port <= to_port):
                            continue

                        open_cidrs = (
                            [r["CidrIp"]   for r in rule.get("IpRanges",   []) if r.get("CidrIp")   in OPEN_CIDRS] +
                            [r["CidrIpv6"] for r in rule.get("Ipv6Ranges", []) if r.get("CidrIpv6") in OPEN_CIDRS]
                        )

                        for cidr in open_cidrs:
                            findings.append(self._sg_finding(
                                sg_id, sg_name, vpc_id, tags,
                                port=port, service=service,
                                cidr=cidr, severity="critical",
                                from_port=from_port, to_port=to_port,
                            ))

        return findings

    def _sg_finding(
        self,
        sg_id: str,
        sg_name: str,
        vpc_id: str,
        tags: Dict[str, str],
        port: Any,
        service: str,
        cidr: str,
        severity: str,
        from_port: int,
        to_port: int,
    ) -> Finding:
        return self._build_finding(
            domain="security",
            category="network",
            severity=severity,
            resource_id=sg_id,
            resource_type="AWS::EC2::SecurityGroup",
            title=f"Puerto {service} ({port}) abierto al mundo en SG: {sg_name}",
            description=(
                f"El Security Group '{sg_name}' ({sg_id}) tiene el puerto "
                f"{port} ({service}) abierto a {cidr}, permitiendo acceso "
                f"desde cualquier IP en internet. Esto expone el servicio "
                f"a ataques de fuerza bruta, exploits y accesos no autorizados."
            ),
            recommendation=(
                f"Restringir el acceso al puerto {port} ({service}) solo a IPs "
                f"específicas conocidas o usar AWS Systems Manager Session Manager "
                f"para SSH/RDP sin necesidad de abrir puertos. "
                f"Para bases de datos, acceder solo desde SGs internos."
            ),
            owner=self._get_tag(tags, "owner"),
            project=self._get_tag(tags, "project"),
            environment=self._get_tag(tags, "environment"),
            cost_center=self._get_tag(tags, "costcenter"),
            evidence={
                "security_group_id":   sg_id,
                "security_group_name": sg_name,
                "vpc_id":              vpc_id,
                "port":                port,
                "service":             service,
                "open_cidr":           cidr,
                "from_port":           from_port,
                "to_port":             to_port,
            },
        )

    # ------------------------------------------------------------------
    # Check 2: VPCs sin Flow Logs
    # ------------------------------------------------------------------
    def _check_vpc_flow_logs(self) -> List[Finding]:
        findings = []
        try:
            # Obtener todas las VPCs
            paginator = self.ec2.get_paginator("describe_vpcs")
            vpcs = []
            for page in paginator.paginate():
                vpcs.extend(page.get("Vpcs", []))

            # Obtener todos los flow logs activos
            fl_resp = self.ec2.describe_flow_logs(
                Filters=[{"Name": "resource-type", "Values": ["VPC"]}]
            )
            vpcs_with_logs = {
                fl["ResourceId"]
                for fl in fl_resp.get("FlowLogs", [])
                if fl.get("FlowLogStatus") == "ACTIVE"
            }

            for vpc in vpcs:
                vpc_id   = vpc["VpcId"]
                is_default = vpc.get("IsDefault", False)
                tags     = self._extract_tags(vpc.get("Tags", []))
                vpc_name = self._get_tag(tags, "name") or vpc_id

                if vpc_id not in vpcs_with_logs:
                    findings.append(
                        self._build_finding(
                            domain="security",
                            category="network",
                            severity="medium",
                            resource_id=vpc_id,
                            resource_type="AWS::EC2::VPC",
                            title=f"VPC sin Flow Logs activos: {vpc_name}",
                            description=(
                                f"La VPC '{vpc_name}' ({vpc_id}) no tiene VPC Flow Logs "
                                f"activos. Sin flow logs no es posible auditar el tráfico "
                                f"de red, detectar comunicaciones sospechosas ni responder "
                                f"a incidentes de seguridad con evidencia."
                            ),
                            recommendation=(
                                f"Habilitar VPC Flow Logs para '{vpc_id}': "
                                f"VPC → {vpc_id} → Flow logs → Create flow log. "
                                f"Configurar destino en CloudWatch Logs o S3 con "
                                f"retención mínima de 90 días."
                            ),
                            owner=self._get_tag(tags, "owner"),
                            project=self._get_tag(tags, "project"),
                            environment=self._get_tag(tags, "environment"),
                            cost_center=self._get_tag(tags, "costcenter"),
                            evidence={
                                "vpc_id":     vpc_id,
                                "vpc_name":   vpc_name,
                                "is_default": is_default,
                                "cidr_block": vpc.get("CidrBlock"),
                                "flow_logs":  "not_configured",
                            },
                        )
                    )
        except Exception as e:
            self.logger.warning(
                "Error verificando VPC Flow Logs",
                extra={"error": str(e)},
            )

        return findings
