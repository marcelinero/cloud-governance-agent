"""
logging_checker.py — Auditoría de trazabilidad y logging en AWS.

Checks implementados:
  - [CRITICAL] CloudTrail deshabilitado o sin trails activos en la región
  - [MEDIUM]   Funciones Lambda sin log group con retención configurada
"""

from __future__ import annotations

from typing import Any, Dict, List

from botocore.exceptions import ClientError

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory


class LoggingChecker(BaseChecker):
    """Audita la configuración de logging y trazabilidad en la cuenta AWS."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.cloudtrail  = factory.get_client("cloudtrail")
        self.lambda_     = factory.get_client("lambda")
        self.logs        = factory.get_client("logs")

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de logging y trazabilidad."""
        self.logger.info("Iniciando LoggingChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []

        try:
            findings.extend(self._check_cloudtrail())
            findings.extend(self._check_lambda_logging())
        except Exception as e:
            self.logger.error("Error en LoggingChecker", extra={"error": str(e)})

        self.logger.info(
            "LoggingChecker completado",
            extra={"findings": len(findings)},
        )
        return findings

    # ------------------------------------------------------------------
    # Check 1: CloudTrail habilitado y activo
    # ------------------------------------------------------------------
    def _check_cloudtrail(self) -> List[Finding]:
        findings = []
        try:
            trails_resp = self.cloudtrail.describe_trails(includeShadowTrails=False)
            trails = trails_resp.get("trailList", [])

            if not trails:
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="logging",
                        severity="critical",
                        resource_id=f"arn:aws:cloudtrail:{self.region}:{self.account_id}:trail",
                        resource_type="AWS::CloudTrail::Trail",
                        title=f"CloudTrail no configurado en región {self.region}",
                        description=(
                            f"No existe ningún trail de CloudTrail en la región "
                            f"'{self.region}'. Sin CloudTrail no hay registro de "
                            f"llamadas a la API AWS, imposibilitando la auditoría, "
                            f"detección de incidentes y cumplimiento regulatorio."
                        ),
                        recommendation=(
                            f"Crear un trail de CloudTrail en la región '{self.region}': "
                            f"CloudTrail → Create trail → Multi-region trail habilitado. "
                            f"Configurar destino S3 con retención mínima de 1 año y "
                            f"habilitar Log File Validation."
                        ),
                        evidence={
                            "region": self.region,
                            "trails_found": 0,
                        },
                    )
                )
                return findings

            # Verificar que al menos un trail esté activo y registrando
            active_trails = []
            for trail in trails:
                trail_name = trail.get("Name", "unknown")
                trail_arn  = trail.get("TrailARN", "")
                try:
                    status = self.cloudtrail.get_trail_status(Name=trail_arn or trail_name)
                    is_logging = status.get("IsLogging", False)
                    if is_logging:
                        active_trails.append(trail_name)
                    else:
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="logging",
                                severity="critical",
                                resource_id=trail_arn,
                                resource_type="AWS::CloudTrail::Trail",
                                title=f"CloudTrail detenido: {trail_name}",
                                description=(
                                    f"El trail de CloudTrail '{trail_name}' existe pero "
                                    f"NO está registrando eventos (IsLogging=False). "
                                    f"Las acciones realizadas en la cuenta no están "
                                    f"siendo auditadas."
                                ),
                                recommendation=(
                                    f"Reactivar el trail '{trail_name}': "
                                    f"CloudTrail → Trails → {trail_name} → Start logging."
                                ),
                                evidence={
                                    "trail_name":   trail_name,
                                    "trail_arn":    trail_arn,
                                    "is_logging":   False,
                                    "latest_delivery": status.get("LatestDeliveryTime", "N/A"),
                                },
                            )
                        )
                except Exception as e:
                    self.logger.warning(
                        "Error verificando estado de trail",
                        extra={"trail": trail_name, "error": str(e)},
                    )

        except Exception as e:
            self.logger.error("Error verificando CloudTrail", extra={"error": str(e)})

        return findings

    # ------------------------------------------------------------------
    # Check 2: Lambda sin log group con retención
    # ------------------------------------------------------------------
    def _check_lambda_logging(self) -> List[Finding]:
        findings = []
        try:
            # Obtener todos los log groups de Lambda existentes con retención
            log_groups_with_retention: Dict[str, int] = {}
            paginator = self.logs.get_paginator("describe_log_groups")
            for page in paginator.paginate(logGroupNamePrefix="/aws/lambda/"):
                for lg in page.get("logGroups", []):
                    name       = lg["logGroupName"]
                    retention  = lg.get("retentionInDays")
                    log_groups_with_retention[name] = retention  # None = sin retención

            # Iterar sobre todas las funciones Lambda
            paginator_fn = self.lambda_.get_paginator("list_functions")
            for page in paginator_fn.paginate():
                for fn in page.get("Functions", []):
                    fn_name = fn["FunctionName"]
                    fn_arn  = fn["FunctionArn"]
                    tags    = self._get_lambda_tags(fn_arn)
                    log_group_name = f"/aws/lambda/{fn_name}"

                    if log_group_name not in log_groups_with_retention:
                        # Log group no existe — Lambda nunca ha sido invocada o fue borrado
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="logging",
                                severity="medium",
                                resource_id=fn_arn,
                                resource_type="AWS::Lambda::Function",
                                title=f"Lambda sin log group configurado: {fn_name}",
                                description=(
                                    f"La función Lambda '{fn_name}' no tiene log group "
                                    f"en CloudWatch Logs ({log_group_name}). Sin logs "
                                    f"no es posible auditar las invocaciones ni depurar "
                                    f"errores de la función."
                                ),
                                recommendation=(
                                    f"Crear el log group '{log_group_name}' con retención "
                                    f"configurada (90 días recomendado) antes de invocar la función, "
                                    f"o invocar la función para que CloudWatch lo cree automáticamente "
                                    f"y luego configurar la retención."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={
                                    "function_name":   fn_name,
                                    "log_group":       log_group_name,
                                    "log_group_exists": False,
                                    "runtime":         fn.get("Runtime"),
                                },
                            )
                        )
                    elif log_groups_with_retention[log_group_name] is None:
                        # Log group existe pero sin política de retención
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="logging",
                                severity="medium",
                                resource_id=fn_arn,
                                resource_type="AWS::Lambda::Function",
                                title=f"Lambda sin retención de logs configurada: {fn_name}",
                                description=(
                                    f"La función Lambda '{fn_name}' tiene log group en "
                                    f"CloudWatch pero sin política de retención. Los logs "
                                    f"se acumulan indefinidamente generando costos crecientes "
                                    f"y dificultando la búsqueda de eventos relevantes."
                                ),
                                recommendation=(
                                    f"Configurar retención en '{log_group_name}': "
                                    f"CloudWatch → Log groups → {log_group_name} → "
                                    f"Edit retention setting → 90 días recomendado."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={
                                    "function_name":      fn_name,
                                    "log_group":          log_group_name,
                                    "log_group_exists":   True,
                                    "retention_days":     None,
                                    "runtime":            fn.get("Runtime"),
                                },
                            )
                        )

        except Exception as e:
            self.logger.error(
                "Error verificando Lambda logging",
                extra={"error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Helper: obtener tags de una función Lambda
    # ------------------------------------------------------------------
    def _get_lambda_tags(self, function_arn: str) -> Dict[str, str]:
        try:
            resp = self.lambda_.list_tags(Resource=function_arn)
            raw_tags = [
                {"Key": k, "Value": v}
                for k, v in resp.get("Tags", {}).items()
            ]
            return self._extract_tags(raw_tags)
        except Exception:
            return {}
