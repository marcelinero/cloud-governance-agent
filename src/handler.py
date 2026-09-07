"""
handler.py — Orquestador principal del Cloud Governance Agent (CGA).

Entry point de la función Lambda. Coordina la ejecución paralela de
los checkers, la agregación de hallazgos, la generación del reporte
y el envío de notificaciones.

Flujo:
  1. Inicializar logger, configuración y clientes AWS
  2. Ejecutar SecurityCheckers + FinOpsCheckers + ComplianceCheckers en paralelo
  3. Aggregator: consolidar, deduplicar y ordenar hallazgos
  4. ReportGenerator: generar JSON (S3) + HTML
  5. Notifier: enviar emails segmentados por rol
  6. Publicar métricas en CloudWatch
  7. Retornar resumen
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.checkers.compliance.tagging_checker    import TaggingChecker
from src.checkers.finops.dynamodb_checker       import DynamoDBChecker
from src.checkers.finops.ec2_checker            import EC2FinOpsChecker
from src.checkers.finops.lambda_checker         import LambdaFinOpsChecker
from src.checkers.finops.network_checker        import NetworkFinOpsChecker
from src.checkers.finops.rds_checker            import RDSFinOpsChecker
from src.checkers.finops.storage_checker        import StorageChecker
from src.checkers.security.cloudfront_checker   import CloudFrontChecker
from src.checkers.security.iam_checker          import IAMChecker
from src.checkers.security.logging_checker      import LoggingChecker
from src.checkers.security.network_checker      import NetworkChecker
from src.checkers.security.rds_checker          import RDSSecurityChecker
from src.checkers.security.s3_checker           import S3SecurityChecker
from src.core.aggregator                        import Aggregator
from src.core.models                            import Report
from src.core.notifier                          import Notifier
from src.core.report_generator                  import ReportGenerator
from src.utils.aws_client                       import build_factory
from src.utils.logger                           import get_logger

logger = get_logger("cga.handler")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Entry point de la Lambda del Cloud Governance Agent.

    Args:
        event:   Payload del trigger. Puede incluir:
                   - execution_type: "scheduled" | "on-demand"
                   - source: "eventbridge" | "manual"
        context: Contexto Lambda (timeout, function_name, etc.)

    Returns:
        Dict con resumen de la ejecución:
          {
            "status": "success" | "error",
            "report_id": str,
            "total_findings": int,
            "critical": int,
            "potential_saving_usd": float,
            "duration_seconds": float,
            "s3_key": str,
            "notifications_sent": dict,
          }
    """
    start_time     = time.time()
    execution_type = event.get("execution_type", "on-demand")

    logger.info("CGA iniciado", extra={
        "execution_type": execution_type,
        "event":          event,
    })

    # ------------------------------------------------------------------
    # 1. Configuración desde variables de entorno
    # ------------------------------------------------------------------
    region       = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    account_name = os.environ.get("AWS_ACCOUNT_NAME", "AWS Account")
    bucket_name  = os.environ.get("REPORTS_BUCKET", "")

    config: Dict[str, Any] = {
        "region":                   region,
        "account_name":             account_name,
        "cpu_threshold_percent":    int(os.environ.get("CPU_THRESHOLD_PERCENT",   "10")),
        "stopped_days_threshold":   int(os.environ.get("STOPPED_DAYS_THRESHOLD",  "7")),
        "key_age_days_threshold":   int(os.environ.get("KEY_AGE_DAYS_THRESHOLD",  "90")),
        "lambda_inactive_days":     int(os.environ.get("LAMBDA_INACTIVE_DAYS",    "30")),
        "snapshot_age_days":        int(os.environ.get("SNAPSHOT_AGE_DAYS",       "30")),
        "ami_age_days":             int(os.environ.get("AMI_AGE_DAYS",            "90")),
        "dynamodb_ops_threshold":   int(os.environ.get("DYNAMODB_OPS_THRESHOLD",  "10")),
        "inactive_days_threshold":  int(os.environ.get("INACTIVE_DAYS_THRESHOLD", "90")),
    }

    # ------------------------------------------------------------------
    # 2. Inicializar factory y resolver account_id
    # ------------------------------------------------------------------
    factory    = build_factory(region=region)
    account_id = factory.get_account_id()
    config["account_id"] = account_id

    logger.info("Configuración cargada", extra={
        "account_id": account_id, "region": region,
    })

    # ------------------------------------------------------------------
    # 3. Definir grupos de checkers
    # ------------------------------------------------------------------
    security_checkers = [
        IAMChecker(factory, config),
        S3SecurityChecker(factory, config),
        NetworkChecker(factory, config),
        RDSSecurityChecker(factory, config),
        CloudFrontChecker(factory, config),
        LoggingChecker(factory, config),
    ]

    finops_checkers = [
        EC2FinOpsChecker(factory, config),
        RDSFinOpsChecker(factory, config),
        LambdaFinOpsChecker(factory, config),
        StorageChecker(factory, config),
        NetworkFinOpsChecker(factory, config),
        DynamoDBChecker(factory, config),
    ]

    compliance_checkers = [
        TaggingChecker(factory, config),
    ]

    # ------------------------------------------------------------------
    # 4. Ejecutar checkers en paralelo (3 grupos simultáneos)
    # ------------------------------------------------------------------
    all_findings = []

    def run_group(checkers: list, group_name: str) -> List:
        group_findings = []
        for checker in checkers:
            try:
                results = checker.run()
                group_findings.extend(results)
                logger.info(
                    f"Checker completado",
                    extra={
                        "checker":  checker.__class__.__name__,
                        "group":    group_name,
                        "findings": len(results),
                    },
                )
            except Exception as e:
                logger.error(
                    f"Error en checker",
                    extra={
                        "checker": checker.__class__.__name__,
                        "group":   group_name,
                        "error":   str(e),
                    },
                )
        return group_findings

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_group, security_checkers,    "security"):   "security",
            executor.submit(run_group, finops_checkers,      "finops"):     "finops",
            executor.submit(run_group, compliance_checkers,  "compliance"): "compliance",
        }
        for future in as_completed(futures):
            group = futures[future]
            try:
                findings = future.result()
                all_findings.extend(findings)
                logger.info(f"Grupo completado",
                            extra={"group": group, "findings": len(findings)})
            except Exception as e:
                logger.error(f"Error en grupo",
                             extra={"group": group, "error": str(e)})

    logger.info("Todos los checkers completados",
                extra={"total_raw_findings": len(all_findings)})

    # ------------------------------------------------------------------
    # 5. Aggregator
    # ------------------------------------------------------------------
    aggregator             = Aggregator()
    sorted_findings, summary = aggregator.aggregate(all_findings)

    # ------------------------------------------------------------------
    # 6. Construir objeto Report
    # ------------------------------------------------------------------
    duration = time.time() - start_time
    report   = Report(
        account_id=account_id,
        account_name=account_name,
        region=region,
        execution_type=execution_type,
        summary=summary,
        findings=sorted_findings,
        duration_seconds=duration,
    )

    # ------------------------------------------------------------------
    # 7. ReportGenerator → JSON a S3 + HTML
    # ------------------------------------------------------------------
    s3_key    = ""
    html_body = ""
    try:
        generator = ReportGenerator(bucket_name=bucket_name)
        s3_key, html_body = generator.generate(report)
    except Exception as e:
        logger.error("Error generando reporte", extra={"error": str(e)})

    # ------------------------------------------------------------------
    # 8. Notifier → emails segmentados por rol
    # ------------------------------------------------------------------
    notifications_sent: Dict[str, int] = {}
    try:
        notifier = Notifier()
        notifications_sent = notifier.notify(report, html_body, s3_key)
    except Exception as e:
        logger.error("Error enviando notificaciones", extra={"error": str(e)})

    # ------------------------------------------------------------------
    # 9. Publicar métricas en CloudWatch
    # ------------------------------------------------------------------
    try:
        _publish_metrics(factory, report, duration)
    except Exception as e:
        logger.warning("Error publicando métricas", extra={"error": str(e)})

    # ------------------------------------------------------------------
    # 10. Retornar resumen
    # ------------------------------------------------------------------
    result = {
        "status":               "success",
        "report_id":            report.report_id,
        "account_id":           account_id,
        "total_findings":       summary.total_findings,
        "critical":             summary.critical,
        "high":                 summary.high,
        "medium":               summary.medium,
        "low":                  summary.low,
        "potential_saving_usd": summary.total_potential_saving,
        "duration_seconds":     round(duration, 2),
        "s3_key":               s3_key,
        "notifications_sent":   notifications_sent,
        "findings_by_domain":   summary.findings_by_domain,
    }

    logger.info("CGA completado exitosamente", extra=result)
    return result


def _publish_metrics(factory, report: Report, duration: float) -> None:
    """Publica métricas de ejecución en CloudWatch."""
    cw = factory.get_client("cloudwatch")
    ts = datetime.now(timezone.utc)

    metrics = [
        ("TotalFindings",       report.summary.total_findings,         "Count"),
        ("CriticalFindings",    report.summary.critical,                "Count"),
        ("HighFindings",        report.summary.high,                    "Count"),
        ("PotentialSavingUSD",  report.summary.total_potential_saving,  "None"),
        ("ExecutionDurationS",  duration,                               "Seconds"),
    ]

    metric_data = [
        {
            "MetricName": name,
            "Value":      value,
            "Unit":       unit,
            "Timestamp":  ts,
            "Dimensions": [
                {"Name": "AccountId", "Value": report.account_id},
                {"Name": "Region",    "Value": report.region},
            ],
        }
        for name, value, unit in metrics
    ]

    cw.put_metric_data(Namespace="CGA/Audit", MetricData=metric_data)
    logger.info("Métricas publicadas en CloudWatch",
                extra={"metrics_count": len(metric_data)})
