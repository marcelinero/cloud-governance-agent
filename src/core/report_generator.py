"""
report_generator.py — Genera reportes HTML y JSON del Cloud Governance Agent.

Produce dos artefactos:
  - JSON: reporte completo con evidencias, subido a S3
  - HTML: reporte visual con resumen ejecutivo y tablas por dominio
          con estilos CSS inline para compatibilidad con clientes de email
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Tuple

import boto3

from src.core.models import Finding, Report, ReportSummary
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Colores por severidad
SEVERITY_COLORS = {
    "critical": "#dc2626",  # rojo
    "high":     "#ea580c",  # naranja
    "medium":   "#d97706",  # amarillo
    "low":      "#2563eb",  # azul
}
SEVERITY_BG = {
    "critical": "#fef2f2",
    "high":     "#fff7ed",
    "medium":   "#fffbeb",
    "low":      "#eff6ff",
}


class ReportGenerator:
    """Genera reportes en formato JSON (S3) y HTML (email)."""

    def __init__(self, s3_client=None, bucket_name: str = "") -> None:
        self.s3     = s3_client or boto3.client("s3")
        self.bucket = bucket_name or os.environ.get("REPORTS_BUCKET", "")

    def generate(self, report: Report) -> Tuple[str, str, str]:
        """
        Genera el reporte en JSON y HTML, sube ambos a S3 y retorna las claves.

        El nombre de los archivos incluye la fecha y hora de ejecución (UTC) para
        facilitar la trazabilidad y la identificación cronológica de los reportes:
            YYYY/MM/DD/cga-report-YYYY-MM-DD_HHMMSS-<id-corto>.{json,html}

        Args:
            report: Objeto Report completo con findings y summary.

        Returns:
            Tuple[str, str, str]: (s3_key del JSON, s3_key del HTML, html_content)
        """
        # Nombre base compartido con timestamp legible para trazabilidad
        dt         = datetime.now(timezone.utc)
        short_id   = report.report_id[:8]
        prefix     = f"{dt.year}/{dt.month:02d}/{dt.day:02d}"
        base_name  = f"cga-report-{dt.strftime('%Y-%m-%d_%H%M%S')}-{short_id}"

        json_key = f"{prefix}/{base_name}.json"
        html_key = f"{prefix}/{base_name}.html"

        html_str = self._generate_html(report)

        self._upload_json(report, json_key)
        self._upload_html(html_str, html_key)

        return json_key, html_key, html_str

    # ------------------------------------------------------------------
    # JSON → S3
    # ------------------------------------------------------------------
    def _upload_json(self, report: Report, s3_key: str) -> str:
        """Serializa el reporte a JSON y lo sube a S3."""
        body = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )
            logger.info("Reporte JSON subido a S3",
                        extra={"bucket": self.bucket, "key": s3_key})
        except Exception as e:
            logger.error("Error subiendo reporte JSON a S3", extra={"error": str(e)})
        return s3_key

    # ------------------------------------------------------------------
    # HTML → S3
    # ------------------------------------------------------------------
    def _upload_html(self, html_str: str, s3_key: str) -> str:
        """Sube el reporte HTML a S3 (visualizable en navegador)."""
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=html_str.encode("utf-8"),
                ContentType="text/html; charset=utf-8",
                ServerSideEncryption="AES256",
            )
            logger.info("Reporte HTML subido a S3",
                        extra={"bucket": self.bucket, "key": s3_key})
        except Exception as e:
            logger.error("Error subiendo reporte HTML a S3", extra={"error": str(e)})
        return s3_key

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------
    def _generate_html(self, report: Report) -> str:
        """Genera el reporte HTML completo con estilos inline."""
        s = report.summary
        top5_savings = sorted(
            [f for f in report.findings if f.potential_saving > 0],
            key=lambda f: f.potential_saving,
            reverse=True,
        )[:5]

        security_findings   = [f for f in report.findings if f.domain == "security"]
        finops_findings     = [f for f in report.findings if f.domain == "finops"]
        compliance_findings = [f for f in report.findings if f.domain == "compliance"]

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cloud Governance Agent — Reporte {report.generated_at[:10]}</title>
</head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px;color:#1e293b;">

<!-- HEADER -->
<div style="background:#1e293b;color:#fff;padding:24px 32px;border-radius:8px;margin-bottom:24px;">
  <h1 style="margin:0;font-size:24px;">☁️ Cloud Governance Agent</h1>
  <p style="margin:8px 0 0;color:#94a3b8;font-size:14px;">
    Reporte de Auditoría — {report.account_name} ({report.account_id}) |
    {report.generated_at[:19].replace("T"," ")} UTC |
    Ejecución: {report.execution_type}
  </p>
</div>

<!-- RESUMEN EJECUTIVO -->
<div style="background:#fff;border-radius:8px;padding:24px;margin-bottom:24px;border:1px solid #e2e8f0;">
  <h2 style="margin:0 0 16px;font-size:18px;color:#1e293b;">📊 Resumen Ejecutivo</h2>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
    {self._summary_card("🔴 Critical", s.critical, "#dc2626", "#fef2f2")}
    {self._summary_card("🟠 High",     s.high,     "#ea580c", "#fff7ed")}
    {self._summary_card("🟡 Medium",   s.medium,   "#d97706", "#fffbeb")}
    {self._summary_card("🔵 Low",      s.low,      "#2563eb", "#eff6ff")}
  </div>
  <div style="margin-top:16px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
    {self._summary_card("📋 Total Hallazgos", s.total_findings, "#475569", "#f1f5f9")}
    {self._summary_card("💰 Costo Estimado",  f"${s.total_estimated_cost:,.2f}/mes", "#059669", "#ecfdf5")}
    {self._summary_card("💡 Ahorro Potencial", f"${s.total_potential_saving:,.2f}/mes", "#7c3aed", "#f5f3ff")}
  </div>
</div>

<!-- TOP 5 AHORROS -->
{self._top5_section(top5_savings) if top5_savings else ""}

<!-- HALLAZGOS SEGURIDAD -->
{self._domain_section("🔐 Seguridad", security_findings, "security") if security_findings else ""}

<!-- HALLAZGOS FINOPS -->
{self._domain_section("💰 FinOps — Optimización de Costos", finops_findings, "finops") if finops_findings else ""}

<!-- HALLAZGOS CUMPLIMIENTO -->
{self._domain_section("🏷️ Cumplimiento de Etiquetado", compliance_findings, "compliance") if compliance_findings else ""}

<!-- FOOTER -->
<div style="text-align:center;padding:16px;color:#94a3b8;font-size:12px;margin-top:24px;">
  Cloud Governance Agent v1.0 | Generado el {report.generated_at[:19].replace("T"," ")} UTC |
  Duración: {report.duration_seconds:.1f}s |
  Reporte ID: {report.report_id}
</div>

</body>
</html>"""
        return html

    def _summary_card(self, label: str, value, color: str, bg: str) -> str:
        return (
            f'<div style="background:{bg};border:1px solid {color}33;border-radius:6px;'
            f'padding:12px;text-align:center;">'
            f'<div style="font-size:22px;font-weight:bold;color:{color};">{value}</div>'
            f'<div style="font-size:12px;color:#475569;margin-top:4px;">{label}</div>'
            f'</div>'
        )

    def _top5_section(self, findings: List[Finding]) -> str:
        rows = ""
        for f in findings:
            rows += (
                f'<tr>'
                f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;">{f.title}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;">{f.resource_id}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;color:#059669;font-weight:bold;">'
                f'${f.potential_saving:,.2f}/mes</td>'
                f'</tr>'
            )
        return f"""
<div style="background:#fff;border-radius:8px;padding:24px;margin-bottom:24px;border:1px solid #e2e8f0;">
  <h2 style="margin:0 0 16px;font-size:18px;color:#1e293b;">💡 Top 5 Oportunidades de Ahorro</h2>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:#f1f5f9;">
        <th style="padding:8px;text-align:left;color:#475569;">Hallazgo</th>
        <th style="padding:8px;text-align:left;color:#475569;">Recurso</th>
        <th style="padding:8px;text-align:left;color:#475569;">Ahorro potencial</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

    def _domain_section(self, title: str, findings: List[Finding], domain: str) -> str:
        rows = ""
        for f in findings:
            sev_color = SEVERITY_COLORS.get(f.severity, "#475569")
            sev_bg    = SEVERITY_BG.get(f.severity, "#f1f5f9")
            cost_cell = (
                f'<span style="color:#059669;">${f.potential_saving:,.2f}/mes</span>'
                if f.potential_saving > 0 else "—"
            )
            rows += (
                f'<tr>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;">'
                f'  <span style="background:{sev_bg};color:{sev_color};padding:2px 8px;'
                f'border-radius:12px;font-size:11px;font-weight:bold;">'
                f'{f.severity.upper()}</span></td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;font-size:13px;">'
                f'<strong>{f.title}</strong><br>'
                f'<span style="color:#64748b;font-size:11px;">{f.resource_id}</span></td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;font-size:12px;color:#475569;">'
                f'{f.recommendation[:120]}...</td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;font-size:12px;">'
                f'{f.owner}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;font-size:12px;">'
                f'{cost_cell}</td>'
                f'</tr>'
            )

        return f"""
<div style="background:#fff;border-radius:8px;padding:24px;margin-bottom:24px;border:1px solid #e2e8f0;">
  <h2 style="margin:0 0 4px;font-size:18px;color:#1e293b;">{title}</h2>
  <p style="margin:0 0 16px;color:#64748b;font-size:13px;">{len(findings)} hallazgo(s)</p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:#f8fafc;">
        <th style="padding:8px;text-align:left;color:#475569;width:90px;">Severidad</th>
        <th style="padding:8px;text-align:left;color:#475569;">Hallazgo / Recurso</th>
        <th style="padding:8px;text-align:left;color:#475569;">Recomendación</th>
        <th style="padding:8px;text-align:left;color:#475569;width:120px;">Owner</th>
        <th style="padding:8px;text-align:left;color:#475569;width:100px;">Ahorro</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""
