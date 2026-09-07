"""
rds_checker.py — Auditoría de seguridad de Amazon RDS.

Checks implementados:
  - [HIGH] Instancias RDS con PubliclyAccessible = True
  - [HIGH] Instancias RDS sin Multi-AZ en entorno production
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory


class RDSSecurityChecker(BaseChecker):
    """Audita configuraciones de seguridad de instancias RDS."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.rds = factory.get_client("rds")

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de seguridad RDS."""
        self.logger.info("Iniciando RDSSecurityChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []

        try:
            paginator = self.rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for instance in page.get("DBInstances", []):
                    try:
                        tags = self._get_rds_tags(instance["DBInstanceArn"])
                        findings.extend(self._check_publicly_accessible(instance, tags))
                        findings.extend(self._check_multi_az(instance, tags))
                    except Exception as e:
                        self.logger.warning(
                            "Error auditando instancia RDS",
                            extra={"instance": instance.get("DBInstanceIdentifier"), "error": str(e)},
                        )
        except Exception as e:
            self.logger.error("Error en RDSSecurityChecker", extra={"error": str(e)})

        self.logger.info(
            "RDSSecurityChecker completado",
            extra={"findings": len(findings)},
        )
        return findings

    # ------------------------------------------------------------------
    # Check 1: RDS con acceso público
    # ------------------------------------------------------------------
    def _check_publicly_accessible(
        self, instance: Dict, tags: Dict[str, str]
    ) -> List[Finding]:
        findings = []
        db_id    = instance["DBInstanceIdentifier"]
        db_arn   = instance["DBInstanceArn"]
        engine   = instance.get("Engine", "unknown")
        db_class = instance.get("DBInstanceClass", "unknown")

        if instance.get("PubliclyAccessible", False):
            findings.append(
                self._build_finding(
                    domain="security",
                    category="rds",
                    severity="high",
                    resource_id=db_arn,
                    resource_type="AWS::RDS::DBInstance",
                    title=f"RDS con acceso público: {db_id}",
                    description=(
                        f"La instancia RDS '{db_id}' ({engine}, {db_class}) tiene "
                        f"'PubliclyAccessible=True', exponiendo el endpoint de la base "
                        f"de datos a internet. Cualquier IP puede intentar conectarse "
                        f"al puerto de base de datos si el Security Group lo permite."
                    ),
                    recommendation=(
                        f"Deshabilitar el acceso público en '{db_id}': "
                        f"RDS → {db_id} → Modify → Connectivity → Public access → No. "
                        f"Acceder a la base de datos solo desde recursos dentro de la VPC "
                        f"o via bastion host / AWS Systems Manager."
                    ),
                    owner=self._get_tag(tags, "owner"),
                    project=self._get_tag(tags, "project"),
                    environment=self._get_tag(tags, "environment"),
                    cost_center=self._get_tag(tags, "costcenter"),
                    evidence={
                        "db_instance_id":    db_id,
                        "engine":            engine,
                        "db_class":          db_class,
                        "publicly_accessible": True,
                        "endpoint":          instance.get("Endpoint", {}).get("Address", "N/A"),
                        "vpc_id":            instance.get("DBSubnetGroup", {}).get("VpcId", "N/A"),
                        "status":            instance.get("DBInstanceStatus"),
                    },
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Check 2: RDS sin Multi-AZ en producción
    # ------------------------------------------------------------------
    def _check_multi_az(
        self, instance: Dict, tags: Dict[str, str]
    ) -> List[Finding]:
        findings = []
        db_id    = instance["DBInstanceIdentifier"]
        db_arn   = instance["DBInstanceArn"]
        engine   = instance.get("Engine", "unknown")
        env      = self._get_tag(tags, "environment").lower()

        # Solo aplica a entornos productivos
        if env not in ("production", "prod", "prd"):
            return []

        if not instance.get("MultiAZ", False):
            findings.append(
                self._build_finding(
                    domain="security",
                    category="rds",
                    severity="high",
                    resource_id=db_arn,
                    resource_type="AWS::RDS::DBInstance",
                    title=f"RDS sin Multi-AZ en producción: {db_id}",
                    description=(
                        f"La instancia RDS '{db_id}' ({engine}) está en entorno "
                        f"'{env}' pero no tiene Multi-AZ habilitado. Una falla en "
                        f"la zona de disponibilidad causaría downtime no planificado "
                        f"hasta que RDS complete la recuperación (15-30 minutos)."
                    ),
                    recommendation=(
                        f"Habilitar Multi-AZ en '{db_id}': "
                        f"RDS → {db_id} → Modify → Availability & durability → "
                        f"Multi-AZ deployment → Yes. "
                        f"Aplicar durante la próxima ventana de mantenimiento para "
                        f"minimizar el impacto."
                    ),
                    owner=self._get_tag(tags, "owner"),
                    project=self._get_tag(tags, "project"),
                    environment=env,
                    cost_center=self._get_tag(tags, "costcenter"),
                    evidence={
                        "db_instance_id": db_id,
                        "engine":         engine,
                        "multi_az":       False,
                        "environment":    env,
                        "db_class":       instance.get("DBInstanceClass"),
                        "status":         instance.get("DBInstanceStatus"),
                    },
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Helper: obtener tags de una instancia RDS
    # ------------------------------------------------------------------
    def _get_rds_tags(self, resource_arn: str) -> Dict[str, str]:
        try:
            resp = self.rds.list_tags_for_resource(ResourceName=resource_arn)
            return self._extract_tags(resp.get("TagList", []))
        except Exception:
            return {}
