"""
rds_checker.py — Auditoría FinOps de Amazon RDS.

Checks implementados:
  - [HIGH]   Instancias RDS con CPU promedio < umbral en 7 días
  - [HIGH]   Instancias RDS en estado stopped por más de N días
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

# Costo aproximado RDS por clase (USD/hora) — Single-AZ, us-east-1
RDS_HOURLY_COST: Dict[str, float] = {
    "db.t3.micro":   0.017, "db.t3.small":  0.034, "db.t3.medium": 0.068,
    "db.t3.large":   0.136, "db.t3.xlarge": 0.272, "db.t2.micro":  0.017,
    "db.t2.small":   0.034, "db.t2.medium": 0.068, "db.m5.large":  0.171,
    "db.m5.xlarge":  0.342, "db.r5.large":  0.240, "db.r5.xlarge": 0.480,
}
DEFAULT_RDS_HOURLY = 0.10


class RDSFinOpsChecker(BaseChecker):
    """Detecta instancias RDS subutilizadas o detenidas innecesariamente."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.rds           = factory.get_client("rds")
        self.cw            = factory.get_client("cloudwatch")
        self.cpu_threshold = float(config.get("cpu_threshold_percent", 10))
        self.stopped_days  = int(config.get("stopped_days_threshold", 7))
        self.lookback_days = 7

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando RDSFinOpsChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            paginator = self.rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for instance in page.get("DBInstances", []):
                    tags   = self._get_rds_tags(instance["DBInstanceArn"])
                    status = instance.get("DBInstanceStatus", "")
                    if status == "available":
                        findings.extend(self._check_low_cpu(instance, tags))
                    elif status == "stopped":
                        findings.extend(self._check_stopped(instance, tags))
        except Exception as e:
            self.logger.error("Error en RDSFinOpsChecker", extra={"error": str(e)})

        self.logger.info("RDSFinOpsChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # Check 1: CPU bajo en RDS
    # ------------------------------------------------------------------
    def _check_low_cpu(self, instance: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings    = []
        db_id       = instance["DBInstanceIdentifier"]
        db_arn      = instance["DBInstanceArn"]
        db_class    = instance.get("DBInstanceClass", "unknown")
        engine      = instance.get("Engine", "unknown")

        try:
            cpu_avg = self._get_rds_cpu_average(db_id)
            if cpu_avg is None:
                return []

            if cpu_avg < self.cpu_threshold:
                monthly_cost   = self._estimate_monthly_cost(db_class)
                potential_save = round(monthly_cost * 0.5, 2)

                findings.append(
                    self._build_finding(
                        domain="finops",
                        category="rds",
                        severity="high",
                        resource_id=db_arn,
                        resource_type="AWS::RDS::DBInstance",
                        title=f"RDS subutilizada — CPU {cpu_avg:.1f}%: {db_id}",
                        description=(
                            f"La instancia RDS '{db_id}' ({engine}, {db_class}) tiene "
                            f"un promedio de CPU del {cpu_avg:.1f}% en los últimos "
                            f"{self.lookback_days} días (umbral: {self.cpu_threshold}%). "
                            f"Costo mensual estimado: ${monthly_cost:.2f} USD."
                        ),
                        recommendation=(
                            f"Evaluar downgrade a una clase inferior. "
                            f"Usar AWS Compute Optimizer para recomendaciones de RDS. "
                            f"Si la base de datos ya no se usa, hacer snapshot y terminar "
                            f"para ahorrar ~${potential_save:.2f} USD/mes."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        estimated_monthly_cost=monthly_cost,
                        potential_saving=potential_save,
                        evidence={
                            "db_instance_id": db_id,
                            "db_class":       db_class,
                            "engine":         engine,
                            "cpu_avg_pct":    round(cpu_avg, 2),
                            "cpu_threshold":  self.cpu_threshold,
                            "lookback_days":  self.lookback_days,
                        },
                    )
                )
        except Exception as e:
            self.logger.warning("Error verificando CPU RDS",
                                extra={"db": db_id, "error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 2: RDS detenida
    # ------------------------------------------------------------------
    def _check_stopped(self, instance: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings  = []
        db_id     = instance["DBInstanceIdentifier"]
        db_arn    = instance["DBInstanceArn"]
        db_class  = instance.get("DBInstanceClass", "unknown")
        engine    = instance.get("Engine", "unknown")

        # RDS auto-reinicia después de 7 días de stop — advertir de ese comportamiento
        # Usar InstanceCreateTime como proxy si no hay StopTime
        create_time = instance.get("InstanceCreateTime")
        stopped_days = self.stopped_days + 1
        stopped_str  = "Fecha desconocida"

        # Estimar días detenida desde el último evento disponible
        latest_events = []
        try:
            events_resp = self.rds.describe_events(
                SourceIdentifier=db_id,
                SourceType="db-instance",
                Duration=10080,  # últimos 7 días en minutos
            )
            latest_events = events_resp.get("Events", [])
            for event in reversed(latest_events):
                if "stopped" in event.get("Message", "").lower():
                    dt = event.get("Date")
                    if dt:
                        if hasattr(dt, "tzinfo") and dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        stopped_days = (datetime.now(timezone.utc) - dt).days
                        stopped_str  = dt.isoformat()
                        break
        except Exception:
            pass

        if stopped_days >= self.stopped_days:
            monthly_cost   = self._estimate_monthly_cost(db_class)
            # RDS detenida cobra ~20% del costo (almacenamiento)
            stopped_cost   = round(monthly_cost * 0.20, 2)
            potential_save = stopped_cost

            findings.append(
                self._build_finding(
                    domain="finops",
                    category="rds",
                    severity="high",
                    resource_id=db_arn,
                    resource_type="AWS::RDS::DBInstance",
                    title=f"RDS detenida {stopped_days}+ días: {db_id}",
                    description=(
                        f"La instancia RDS '{db_id}' ({engine}, {db_class}) lleva "
                        f"{stopped_days} días detenida (desde: {stopped_str}). "
                        f"⚠️ AWS reinicia automáticamente las instancias RDS después "
                        f"de 7 días de stop. Costo de almacenamiento: ~${stopped_cost:.2f}/mes."
                    ),
                    recommendation=(
                        f"Si la instancia no es necesaria, crear un snapshot final y "
                        f"eliminarla para ahorrar ~${potential_save:.2f} USD/mes. "
                        f"Si se necesita ocasionalmente, considerar Aurora Serverless v2 "
                        f"que escala a cero automáticamente."
                    ),
                    owner=self._get_tag(tags, "owner"),
                    project=self._get_tag(tags, "project"),
                    environment=self._get_tag(tags, "environment"),
                    cost_center=self._get_tag(tags, "costcenter"),
                    estimated_monthly_cost=stopped_cost,
                    potential_saving=potential_save,
                    evidence={
                        "db_instance_id": db_id,
                        "db_class":       db_class,
                        "engine":         engine,
                        "stopped_since":  stopped_str,
                        "stopped_days":   stopped_days,
                        "aws_auto_restart_warning": "RDS auto-restarts after 7 days stopped",
                    },
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_rds_cpu_average(self, db_id: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
            StartTime=start, EndTime=end,
            Period=86400,
            Statistics=["Average"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return None
        return sum(d["Average"] for d in datapoints) / len(datapoints)

    def _estimate_monthly_cost(self, db_class: str) -> float:
        hourly = RDS_HOURLY_COST.get(db_class, DEFAULT_RDS_HOURLY)
        return round(hourly * 730, 2)

    def _get_rds_tags(self, resource_arn: str) -> Dict[str, str]:
        try:
            resp = self.rds.list_tags_for_resource(ResourceName=resource_arn)
            return self._extract_tags(resp.get("TagList", []))
        except Exception:
            return {}
