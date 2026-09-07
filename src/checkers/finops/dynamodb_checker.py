"""
dynamodb_checker.py — Auditoría FinOps de Amazon DynamoDB.

Checks implementados:
  - [LOW]    Tablas con < 10 operaciones read/write por día en 7 días
  - [MEDIUM] Tablas en modo PROVISIONED con capacidad sobredimensionada
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

# Costos DynamoDB us-east-1
DYNAMO_RCU_COST  = 0.00013   # Por RCU/hora en modo PROVISIONED
DYNAMO_WCU_COST  = 0.00065   # Por WCU/hora en modo PROVISIONED


class DynamoDBChecker(BaseChecker):
    """Detecta tablas DynamoDB inactivas o con capacidad sobredimensionada."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.dynamodb     = factory.get_client("dynamodb")
        self.cw           = factory.get_client("cloudwatch")
        self.lookback_days = 7
        self.ops_threshold = int(config.get("dynamodb_ops_threshold", 10))

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando DynamoDBChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            paginator = self.dynamodb.get_paginator("list_tables")
            for page in paginator.paginate():
                for table_name in page.get("TableNames", []):
                    try:
                        table = self.dynamodb.describe_table(TableName=table_name)
                        info  = table["Table"]
                        tags  = self._get_dynamo_tags(info["TableArn"])
                        findings.extend(self._check_inactive_table(info, tags))
                        findings.extend(self._check_overprovisioned(info, tags))
                    except Exception as e:
                        self.logger.warning(
                            "Error auditando tabla DynamoDB",
                            extra={"table": table_name, "error": str(e)},
                        )
        except Exception as e:
            self.logger.error("Error en DynamoDBChecker", extra={"error": str(e)})

        self.logger.info("DynamoDBChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # Check 1: Tablas inactivas (< N ops/día)
    # ------------------------------------------------------------------
    def _check_inactive_table(self, info: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings    = []
        table_name  = info["TableName"]
        table_arn   = info["TableArn"]
        table_status = info.get("TableStatus", "")

        if table_status not in ("ACTIVE",):
            return []

        try:
            reads  = self._get_ops_sum(table_name, "ConsumedReadCapacityUnits")
            writes = self._get_ops_sum(table_name, "ConsumedWriteCapacityUnits")

            if reads is None or writes is None:
                return []

            total_ops = reads + writes
            avg_ops_per_day = total_ops / self.lookback_days if self.lookback_days > 0 else 0

            if avg_ops_per_day < self.ops_threshold:
                billing_mode = info.get("BillingModeSummary", {}).get(
                    "BillingMode", "PROVISIONED"
                )
                # Estimar costo según modo de billing
                monthly_cost = self._estimate_cost(info)

                findings.append(
                    self._build_finding(
                        domain="finops",
                        category="dynamodb",
                        severity="low",
                        resource_id=table_arn,
                        resource_type="AWS::DynamoDB::Table",
                        title=f"Tabla DynamoDB inactiva ({avg_ops_per_day:.1f} ops/día): {table_name}",
                        description=(
                            f"La tabla DynamoDB '{table_name}' tiene un promedio de "
                            f"{avg_ops_per_day:.1f} operaciones/día en los últimos "
                            f"{self.lookback_days} días ({reads:.0f} lecturas + "
                            f"{writes:.0f} escrituras totales). "
                            f"Umbral mínimo: {self.ops_threshold} ops/día. "
                            f"Modo: {billing_mode}. Costo mensual estimado: ${monthly_cost:.2f} USD."
                        ),
                        recommendation=(
                            f"Verificar si la tabla '{table_name}' sigue siendo necesaria. "
                            f"Si está en modo PROVISIONED, cambiar a PAY_PER_REQUEST para "
                            f"eliminar el costo fijo de capacidad. "
                            f"Si no se necesita, exportar los datos y eliminar la tabla."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        estimated_monthly_cost=monthly_cost,
                        potential_saving=round(monthly_cost * 0.8, 2),
                        evidence={
                            "table_name":       table_name,
                            "billing_mode":     billing_mode,
                            "reads_7d":         round(reads, 0),
                            "writes_7d":        round(writes, 0),
                            "avg_ops_per_day":  round(avg_ops_per_day, 2),
                            "ops_threshold":    self.ops_threshold,
                            "table_size_bytes": info.get("TableSizeBytes", 0),
                            "item_count":       info.get("ItemCount", 0),
                        },
                    )
                )
        except Exception as e:
            self.logger.warning(
                "Error verificando actividad DynamoDB",
                extra={"table": table_name, "error": str(e)},
            )
        return findings

    # ------------------------------------------------------------------
    # Check 2: Capacidad PROVISIONED sobredimensionada
    # ------------------------------------------------------------------
    def _check_overprovisioned(self, info: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings   = []
        table_name = info["TableName"]
        table_arn  = info["TableArn"]

        billing_mode = info.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
        if billing_mode != "PROVISIONED":
            return []

        prov = info.get("ProvisionedThroughput", {})
        read_cap  = prov.get("ReadCapacityUnits", 0)
        write_cap = prov.get("WriteCapacityUnits", 0)

        try:
            read_consumed  = self._get_ops_avg(table_name, "ConsumedReadCapacityUnits")
            write_consumed = self._get_ops_avg(table_name, "ConsumedWriteCapacityUnits")

            if read_consumed is None or write_consumed is None:
                return []

            read_util  = (read_consumed  / read_cap  * 100) if read_cap  > 0 else 0
            write_util = (write_consumed / write_cap * 100) if write_cap > 0 else 0

            # Si utilización < 20% en ambos, está sobredimensionada
            if read_util < 20 and write_util < 20 and (read_cap + write_cap) > 10:
                monthly_cost   = self._estimate_cost(info)
                # Con PAY_PER_REQUEST a este nivel de uso costaría ~80% menos
                potential_save = round(monthly_cost * 0.70, 2)

                findings.append(
                    self._build_finding(
                        domain="finops",
                        category="dynamodb",
                        severity="medium",
                        resource_id=table_arn,
                        resource_type="AWS::DynamoDB::Table",
                        title=f"DynamoDB PROVISIONED sobredimensionada: {table_name}",
                        description=(
                            f"La tabla '{table_name}' tiene capacidad PROVISIONED de "
                            f"{read_cap} RCU / {write_cap} WCU pero solo usa "
                            f"{read_util:.1f}% de lecturas y {write_util:.1f}% de escrituras. "
                            f"Costo mensual actual: ~${monthly_cost:.2f} USD."
                        ),
                        recommendation=(
                            f"Cambiar la tabla '{table_name}' a modo PAY_PER_REQUEST "
                            f"(on-demand) para pagar solo por operaciones reales. "
                            f"Ahorro potencial: ~${potential_save:.2f} USD/mes."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        estimated_monthly_cost=monthly_cost,
                        potential_saving=potential_save,
                        evidence={
                            "table_name":        table_name,
                            "billing_mode":      "PROVISIONED",
                            "provisioned_rcu":   read_cap,
                            "provisioned_wcu":   write_cap,
                            "consumed_rcu_avg":  round(read_consumed, 2),
                            "consumed_wcu_avg":  round(write_consumed, 2),
                            "read_utilization":  round(read_util, 1),
                            "write_utilization": round(write_util, 1),
                        },
                    )
                )
        except Exception as e:
            self.logger.warning(
                "Error verificando capacidad DynamoDB",
                extra={"table": table_name, "error": str(e)},
            )
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_ops_sum(self, table_name: str, metric_name: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/DynamoDB",
            MetricName=metric_name,
            Dimensions=[{"Name": "TableName", "Value": table_name}],
            StartTime=start, EndTime=end,
            Period=self.lookback_days * 86400,
            Statistics=["Sum"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0.0
        return sum(d["Sum"] for d in datapoints)

    def _get_ops_avg(self, table_name: str, metric_name: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/DynamoDB",
            MetricName=metric_name,
            Dimensions=[{"Name": "TableName", "Value": table_name}],
            StartTime=start, EndTime=end,
            Period=86400,
            Statistics=["Average"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0.0
        return sum(d["Average"] for d in datapoints) / len(datapoints)

    def _estimate_cost(self, info: Dict) -> float:
        billing_mode = info.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
        if billing_mode == "PROVISIONED":
            prov  = info.get("ProvisionedThroughput", {})
            rcu   = prov.get("ReadCapacityUnits", 0)
            wcu   = prov.get("WriteCapacityUnits", 0)
            return round((rcu * DYNAMO_RCU_COST + wcu * DYNAMO_WCU_COST) * 730, 2)
        return 0.0

    def _get_dynamo_tags(self, resource_arn: str) -> Dict[str, str]:
        try:
            resp = self.dynamodb.list_tags_of_resource(ResourceArn=resource_arn)
            return self._extract_tags(resp.get("Tags", []))
        except Exception:
            return {}
