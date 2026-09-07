"""
ec2_checker.py — Auditoría FinOps de Amazon EC2.

Checks implementados:
  - [HIGH]   Instancias con CPU promedio < umbral en los últimos 7 días
  - [MEDIUM] Instancias en estado stopped por más de N días
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

# Costo aproximado por tipo de instancia (USD/hora) — referencia us-east-1
EC2_HOURLY_COST: Dict[str, float] = {
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208,
    "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664,
    "t3.2xlarge": 0.3328, "t2.micro": 0.0116, "t2.small": 0.023,
    "t2.medium": 0.0464, "t2.large": 0.0928, "m5.large": 0.096,
    "m5.xlarge": 0.192, "m5.2xlarge": 0.384, "c5.large": 0.085,
    "c5.xlarge": 0.17, "r5.large": 0.126, "r5.xlarge": 0.252,
}
DEFAULT_HOURLY_COST = 0.10  # Fallback para tipos no listados


class EC2FinOpsChecker(BaseChecker):
    """Detecta instancias EC2 subutilizadas o detenidas generando costo innecesario."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.ec2 = factory.get_client("ec2")
        self.cw  = factory.get_client("cloudwatch")
        self.cpu_threshold    = float(config.get("cpu_threshold_percent", 10))
        self.stopped_days     = int(config.get("stopped_days_threshold", 7))
        self.lookback_days    = 7

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando EC2FinOpsChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            paginator = self.ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        state = instance["State"]["Name"]
                        tags  = self._extract_tags(instance.get("Tags", []))
                        if state == "running":
                            findings.extend(self._check_low_cpu(instance, tags))
                        elif state == "stopped":
                            findings.extend(self._check_stopped(instance, tags))
        except Exception as e:
            self.logger.error("Error en EC2FinOpsChecker", extra={"error": str(e)})

        self.logger.info("EC2FinOpsChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # Check 1: CPU bajo
    # ------------------------------------------------------------------
    def _check_low_cpu(self, instance: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        instance_id   = instance["InstanceId"]
        instance_type = instance.get("InstanceType", "unknown")
        name          = self._get_tag(tags, "name") or instance_id

        try:
            cpu_avg = self._get_cpu_average(instance_id)
            if cpu_avg is None:
                return []  # Sin métricas disponibles aún

            if cpu_avg < self.cpu_threshold:
                monthly_cost   = self._estimate_monthly_cost(instance_type)
                # Ahorro estimado: diferencia entre tipo actual y uno más pequeño (~60%)
                potential_save = round(monthly_cost * 0.6, 2)

                findings.append(
                    self._build_finding(
                        domain="finops",
                        category="ec2",
                        severity="high",
                        resource_id=instance_id,
                        resource_type="AWS::EC2::Instance",
                        title=f"EC2 subutilizada — CPU {cpu_avg:.1f}%: {name}",
                        description=(
                            f"La instancia '{name}' ({instance_id}, {instance_type}) "
                            f"tiene un promedio de CPU del {cpu_avg:.1f}% en los últimos "
                            f"{self.lookback_days} días (umbral: {self.cpu_threshold}%). "
                            f"Costo mensual estimado: ${monthly_cost:.2f} USD."
                        ),
                        recommendation=(
                            f"Evaluar redimensionamiento (rightsizing) a un tipo de instancia "
                            f"menor. Usar AWS Compute Optimizer para recomendaciones específicas. "
                            f"Si la instancia no es necesaria, terminarla para ahorrar "
                            f"~${potential_save:.2f} USD/mes."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        estimated_monthly_cost=monthly_cost,
                        potential_saving=potential_save,
                        evidence={
                            "instance_id":    instance_id,
                            "instance_type":  instance_type,
                            "cpu_avg_pct":    round(cpu_avg, 2),
                            "cpu_threshold":  self.cpu_threshold,
                            "lookback_days":  self.lookback_days,
                            "launch_time":    str(instance.get("LaunchTime", "")),
                        },
                    )
                )
        except Exception as e:
            self.logger.warning("Error verificando CPU EC2",
                                extra={"instance": instance_id, "error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 2: Instancias detenidas
    # ------------------------------------------------------------------
    def _check_stopped(self, instance: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        instance_id   = instance["InstanceId"]
        instance_type = instance.get("InstanceType", "unknown")
        name          = self._get_tag(tags, "name") or instance_id

        # Usar StateTransitionReason para estimar cuándo fue detenida
        reason     = instance.get("StateTransitionReason", "")
        stopped_dt = self._parse_stop_time(reason)
        if stopped_dt is None:
            # Sin fecha de detención exacta — asumir que cumple el umbral
            stopped_days = self.stopped_days + 1
            stopped_str  = "Fecha desconocida"
        else:
            stopped_days = (datetime.now(timezone.utc) - stopped_dt).days
            stopped_str  = stopped_dt.isoformat()

        if stopped_days >= self.stopped_days:
            # EC2 detenida sigue cobrando EBS adjunto — estimamos ese costo
            ebs_cost       = self._estimate_ebs_cost(instance)
            potential_save = ebs_cost  # Al terminarla, se libera el EBS

            findings.append(
                self._build_finding(
                    domain="finops",
                    category="ec2",
                    severity="medium",
                    resource_id=instance_id,
                    resource_type="AWS::EC2::Instance",
                    title=f"EC2 detenida {stopped_days}+ días: {name}",
                    description=(
                        f"La instancia '{name}' ({instance_id}, {instance_type}) "
                        f"lleva {stopped_days} días en estado stopped (desde: {stopped_str}). "
                        f"Aunque no cobra por cómputo, sigue generando costo por "
                        f"los volúmenes EBS adjuntos (~${ebs_cost:.2f}/mes)."
                    ),
                    recommendation=(
                        f"Si la instancia ya no es necesaria, terminarla para eliminar "
                        f"los costos de almacenamiento EBS. Antes de terminar, crear "
                        f"un snapshot si los datos son necesarios."
                    ),
                    owner=self._get_tag(tags, "owner"),
                    project=self._get_tag(tags, "project"),
                    environment=self._get_tag(tags, "environment"),
                    cost_center=self._get_tag(tags, "costcenter"),
                    estimated_monthly_cost=ebs_cost,
                    potential_saving=potential_save,
                    evidence={
                        "instance_id":   instance_id,
                        "instance_type": instance_type,
                        "stopped_since": stopped_str,
                        "stopped_days":  stopped_days,
                        "threshold_days": self.stopped_days,
                    },
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_cpu_average(self, instance_id: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start, EndTime=end,
            Period=86400,  # 1 día
            Statistics=["Average"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return None
        return sum(d["Average"] for d in datapoints) / len(datapoints)

    def _estimate_monthly_cost(self, instance_type: str) -> float:
        hourly = EC2_HOURLY_COST.get(instance_type, DEFAULT_HOURLY_COST)
        return round(hourly * 730, 2)  # 730 horas/mes

    def _estimate_ebs_cost(self, instance: Dict) -> float:
        total_gb = sum(
            v.get("Ebs", {}).get("VolumeSize", 0)  # gp2/gp3 ~$0.10/GB-mes
            for bdm in instance.get("BlockDeviceMappings", [])
            for v in [bdm] if bdm.get("Ebs")
        )
        # Fallback: asumir 20 GB si no hay info
        if total_gb == 0:
            total_gb = 20
        return round(total_gb * 0.10, 2)

    def _parse_stop_time(self, reason: str) -> Optional[datetime]:
        """Extrae la fecha de detención del campo StateTransitionReason."""
        # Formato: "User initiated (2026-08-01 10:30:00 GMT)"
        import re
        match = re.search(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)", reason)
        if match:
            try:
                return datetime.strptime(
                    match.group(1), "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return None
