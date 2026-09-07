"""
lambda_checker.py — Auditoría FinOps de AWS Lambda.

Checks implementados:
  - [LOW] Funciones Lambda sin invocaciones en los últimos 30 días
  - [LOW] Funciones con Provisioned Concurrency sin uso
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory


class LambdaFinOpsChecker(BaseChecker):
    """Detecta funciones Lambda inactivas o con recursos sobredimensionados."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.lambda_ = factory.get_client("lambda")
        self.cw      = factory.get_client("cloudwatch")
        self.inactive_days = int(config.get("lambda_inactive_days", 30))

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando LambdaFinOpsChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            paginator = self.lambda_.get_paginator("list_functions")
            for page in paginator.paginate():
                for fn in page.get("Functions", []):
                    fn_name = fn["FunctionName"]
                    fn_arn  = fn["FunctionArn"]
                    tags    = self._get_lambda_tags(fn_arn)
                    findings.extend(self._check_unused(fn, tags))
                    findings.extend(self._check_provisioned_concurrency(fn, tags))
        except Exception as e:
            self.logger.error("Error en LambdaFinOpsChecker", extra={"error": str(e)})

        self.logger.info("LambdaFinOpsChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # Check 1: Lambda sin invocaciones
    # ------------------------------------------------------------------
    def _check_unused(self, fn: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings  = []
        fn_name   = fn["FunctionName"]
        fn_arn    = fn["FunctionArn"]
        runtime   = fn.get("Runtime", "unknown")
        memory_mb = fn.get("MemorySize", 128)

        try:
            invocations = self._get_invocation_count(fn_name)
            if invocations is not None and invocations == 0:
                # Costo Lambda ≈ solo si hay invocaciones; costo principal es Provisioned Concurrency
                # Para funciones sin PC el costo es ~$0, pero representan deuda técnica
                findings.append(
                    self._build_finding(
                        domain="finops",
                        category="lambda",
                        severity="low",
                        resource_id=fn_arn,
                        resource_type="AWS::Lambda::Function",
                        title=f"Lambda sin invocaciones {self.inactive_days}+ días: {fn_name}",
                        description=(
                            f"La función Lambda '{fn_name}' ({runtime}, {memory_mb} MB) "
                            f"no ha sido invocada en los últimos {self.inactive_days} días. "
                            f"Aunque Lambda no cobra en reposo, las funciones sin uso "
                            f"representan deuda técnica, superficie de ataque innecesaria "
                            f"y posibles dependencias obsoletas."
                        ),
                        recommendation=(
                            f"Verificar si la función '{fn_name}' sigue siendo necesaria. "
                            f"Si está descontinuada, eliminarla para reducir la superficie "
                            f"de ataque y simplificar el inventario de recursos."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        estimated_monthly_cost=0.0,
                        potential_saving=0.0,
                        evidence={
                            "function_name":    fn_name,
                            "runtime":          runtime,
                            "memory_mb":        memory_mb,
                            "invocations_30d":  0,
                            "inactive_days":    self.inactive_days,
                            "last_modified":    fn.get("LastModified", "unknown"),
                        },
                    )
                )
        except Exception as e:
            self.logger.warning("Error verificando invocaciones Lambda",
                                extra={"function": fn_name, "error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 2: Provisioned Concurrency sin uso
    # ------------------------------------------------------------------
    def _check_provisioned_concurrency(self, fn: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        fn_name  = fn["FunctionName"]
        fn_arn   = fn["FunctionArn"]

        try:
            resp = self.lambda_.list_provisioned_concurrency_configs(FunctionName=fn_name)
            configs = resp.get("ProvisionedConcurrencyConfigs", [])

            for config in configs:
                allocated = config.get("AllocatedProvisionedConcurrentExecutions", 0)
                if allocated == 0:
                    continue

                # Verificar si hubo utilización real
                utilization = self._get_pc_utilization(fn_name)
                if utilization is not None and utilization < 10.0:
                    # Costo PC: ~$0.000064 por GB-segundo (aprox $15/mes por 1 concurrencia con 128MB)
                    memory_gb  = fn.get("MemorySize", 128) / 1024
                    monthly_pc = round(allocated * memory_gb * 0.000064 * 3600 * 730, 2)

                    findings.append(
                        self._build_finding(
                            domain="finops",
                            category="lambda",
                            severity="medium",
                            resource_id=fn_arn,
                            resource_type="AWS::Lambda::Function",
                            title=f"Lambda con Provisioned Concurrency sin uso: {fn_name}",
                            description=(
                                f"La función '{fn_name}' tiene {allocated} unidades de "
                                f"Provisioned Concurrency configuradas pero con utilización "
                                f"del {utilization:.1f}%. "
                                f"Costo mensual estimado: ${monthly_pc:.2f} USD/mes."
                            ),
                            recommendation=(
                                f"Reducir o eliminar la Provisioned Concurrency de '{fn_name}' "
                                f"si no se requiere latencia consistente de arranque en frío. "
                                f"Considerar usar Application Auto Scaling para ajustar "
                                f"automáticamente según demanda real."
                            ),
                            owner=self._get_tag(tags, "owner"),
                            project=self._get_tag(tags, "project"),
                            environment=self._get_tag(tags, "environment"),
                            cost_center=self._get_tag(tags, "costcenter"),
                            estimated_monthly_cost=monthly_pc,
                            potential_saving=monthly_pc,
                            evidence={
                                "function_name":     fn_name,
                                "allocated_pc":      allocated,
                                "pc_utilization_pct": utilization,
                            },
                        )
                    )
        except self.lambda_.exceptions.ResourceNotFoundException:
            pass  # Sin Provisioned Concurrency — OK
        except Exception as e:
            self.logger.warning("Error verificando PC Lambda",
                                extra={"function": fn_name, "error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_invocation_count(self, fn_name: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=self.inactive_days)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Invocations",
            Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
            StartTime=start, EndTime=end,
            Period=self.inactive_days * 86400,
            Statistics=["Sum"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0  # Sin datapoints = sin invocaciones
        return sum(d["Sum"] for d in datapoints)

    def _get_pc_utilization(self, fn_name: str) -> Optional[float]:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        resp  = self.cw.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="ProvisionedConcurrencyUtilization",
            Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
            StartTime=start, EndTime=end,
            Period=86400,
            Statistics=["Average"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0.0
        return sum(d["Average"] for d in datapoints) / len(datapoints)

    def _get_lambda_tags(self, function_arn: str) -> Dict[str, str]:
        try:
            resp = self.lambda_.list_tags(Resource=function_arn)
            raw  = [{"Key": k, "Value": v} for k, v in resp.get("Tags", {}).items()]
            return self._extract_tags(raw)
        except Exception:
            return {}
