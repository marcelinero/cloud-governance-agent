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
        """
        Genera el reporte HTML enriquecido.

        Compatibilidad: un bloque <style> en <head> aporta la experiencia visual
        avanzada (gradientes, hover, barras, responsive) que renderizan los
        navegadores; los estilos inline del cuerpo son el fallback para clientes
        de email que ignoran el <style> del head.
        """
        s = report.summary
        top5_savings = sorted(
            [f for f in report.findings if f.potential_saving > 0],
            key=lambda f: f.potential_saving,
            reverse=True,
        )[:5]

        security_findings   = [f for f in report.findings if f.domain == "security"]
        finops_findings     = [f for f in report.findings if f.domain == "finops"]
        compliance_findings = [f for f in report.findings if f.domain == "compliance"]

        generated = report.generated_at[:19].replace("T", " ")

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cloud Governance Agent — Reporte {report.generated_at[:10]}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: #f1f5f9; margin: 0; padding: 0; color: #1e293b; line-height: 1.5; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }}
  .card {{ background: #fff; border-radius: 14px; padding: 28px; margin-bottom: 24px;
    border: 1px solid #e8edf3; box-shadow: 0 1px 3px rgba(15,23,42,.06), 0 8px 24px rgba(15,23,42,.04); }}
  .hero {{ background: linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#2563eb 130%); color:#fff;
    border-radius:16px; padding:34px 36px; margin-bottom:24px; box-shadow:0 10px 30px rgba(37,99,235,.25); }}
  .hero h1 {{ margin:0; font-size:27px; font-weight:700; letter-spacing:-.3px; }}
  .hero .sub {{ margin:10px 0 0; color:#cbd5e1; font-size:13.5px; }}
  .hero .pills {{ margin-top:18px; display:flex; flex-wrap:wrap; gap:8px; }}
  .pill {{ background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18);
    color:#e2e8f0; padding:5px 12px; border-radius:999px; font-size:12px; }}
  .section-title {{ margin:0 0 4px; font-size:19px; color:#0f172a; font-weight:700; }}
  .section-sub {{ margin:0 0 20px; color:#64748b; font-size:13px; }}
  .grid4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
  .grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:14px; }}
  .metric {{ border-radius:12px; padding:18px 14px; text-align:center;
    transition:transform .15s ease, box-shadow .15s ease; }}
  .metric:hover {{ transform:translateY(-3px); box-shadow:0 8px 20px rgba(15,23,42,.10); }}
  .metric .val {{ font-size:30px; font-weight:800; line-height:1; }}
  .metric .lbl {{ font-size:12px; color:#64748b; margin-top:8px; font-weight:600; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  thead th {{ text-align:left; color:#475569; font-size:11px; text-transform:uppercase;
    letter-spacing:.5px; padding:10px; border-bottom:2px solid #e2e8f0; background:#f8fafc; }}
  tbody td {{ padding:12px 10px; border-bottom:1px solid #eef2f7; vertical-align:top; }}
  tbody tr:nth-child(even) {{ background:#fafbfc; }}
  tbody tr:hover {{ background:#f0f7ff; }}
  .cat-grid {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .footer {{ text-align:center; padding:20px; color:#94a3b8; font-size:12px; }}
  .footer .brand {{ color:#64748b; font-weight:700; }}
  @media (max-width:720px) {{
    .grid4,.grid3 {{ grid-template-columns:repeat(2,1fr); }}
    .hero {{ padding:24px; }} .card {{ padding:20px; }} .hide-mobile {{ display:none; }}
  }}
</style>
</head>
<body style="font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:0;color:#1e293b;">
<div class="wrap">

  <div class="hero" style="background:#0f172a;color:#fff;padding:34px 36px;border-radius:16px;margin-bottom:24px;">
    <h1 style="margin:0;font-size:27px;">&#9729;&#65039; Cloud Governance Agent</h1>
    <p class="sub" style="margin:10px 0 0;color:#cbd5e1;font-size:13.5px;">
      Reporte de auditoría de seguridad, cumplimiento y optimización de costos</p>
    <div class="pills">
      <span class="pill">🏢 {report.account_name}</span>
      <span class="pill">🔑 {report.account_id}</span>
      <span class="pill">🕐 {generated} UTC</span>
      <span class="pill">⚙️ {report.execution_type}</span>
      <span class="pill">⏱️ {report.duration_seconds:.1f}s</span>
    </div>
  </div>

  <div class="card" style="background:#fff;border-radius:14px;padding:28px;margin-bottom:24px;border:1px solid #e8edf3;">
    <h2 class="section-title" style="margin:0 0 4px;font-size:19px;color:#0f172a;">📊 Resumen Ejecutivo</h2>
    <p class="section-sub" style="margin:0 0 20px;color:#64748b;font-size:13px;">
      Distribución de {s.total_findings} hallazgos por severidad</p>
    {self._severity_bar(s)}
    <div class="grid4" style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px;">
      {self._metric("Critical", s.critical, "#dc2626", "#fef2f2")}
      {self._metric("High",     s.high,     "#ea580c", "#fff7ed")}
      {self._metric("Medium",   s.medium,   "#d97706", "#fffbeb")}
      {self._metric("Low",      s.low,      "#2563eb", "#eff6ff")}
    </div>
    <div class="grid3" style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px;">
      {self._metric("Total hallazgos", s.total_findings, "#475569", "#f1f5f9")}
      {self._metric("Costo auditado / mes", f"${s.total_estimated_cost:,.2f}", "#0284c7", "#f0f9ff")}
      {self._metric("Ahorro potencial / mes", f"${s.total_potential_saving:,.2f}", "#059669", "#ecfdf5")}
    </div>
  </div>

  {self._category_section(s)}
  {self._top5_section(top5_savings) if top5_savings else ""}
  {self._domain_section("🔐 Seguridad", security_findings, "#dc2626") if security_findings else ""}
  {self._domain_section("💰 FinOps — Optimización de Costos", finops_findings, "#059669") if finops_findings else ""}
  {self._domain_section("🏷️ Cumplimiento de Etiquetado", compliance_findings, "#7c3aed") if compliance_findings else ""}

  <div class="footer" style="text-align:center;padding:20px;color:#94a3b8;font-size:12px;">
    <span class="brand">Cloud Governance Agent v1.0</span> ·
    Generado el {generated} UTC · Duración {report.duration_seconds:.1f}s<br>
    Reporte ID: {report.report_id}
  </div>

</div>
</body>
</html>"""
        return html

    # ------------------------------------------------------------------
    # Componentes visuales
    # ------------------------------------------------------------------
    def _severity_bar(self, s) -> str:
        """Barra horizontal proporcional a la distribución de severidades."""
        total = max(s.total_findings, 1)
        segs = [
            ("#dc2626", s.critical, "Critical"),
            ("#ea580c", s.high,     "High"),
            ("#d97706", s.medium,   "Medium"),
            ("#2563eb", s.low,      "Low"),
        ]
        bars = "".join(
            f'<span style="display:block;height:100%;width:{(n/total)*100:.1f}%;background:{c};"></span>'
            for c, n, _ in segs if n > 0
        )
        legend = "".join(
            f'<span style="margin-right:16px;">'
            f'<i style="background:{c};width:10px;height:10px;border-radius:50%;'
            f'display:inline-block;margin-right:6px;"></i>{lbl} <b>{n}</b></span>'
            for c, n, lbl in segs
        )
        return (
            f'<div style="display:flex;height:14px;border-radius:999px;overflow:hidden;'
            f'margin:4px 0 10px;background:#e2e8f0;">{bars}</div>'
            f'<div style="font-size:12px;color:#475569;">{legend}</div>'
        )

    def _metric(self, label: str, value, color: str, bg: str) -> str:
        return (
            f'<div class="metric" style="background:{bg};border:1px solid {color}22;'
            f'border-radius:12px;padding:18px 14px;text-align:center;">'
            f'<div class="val" style="font-size:30px;font-weight:800;color:{color};">{value}</div>'
            f'<div class="lbl" style="font-size:12px;color:#64748b;margin-top:8px;">{label}</div>'
            f'</div>'
        )

    def _category_section(self, s) -> str:
        """Muestra el conteo de hallazgos por categoría de servicio AWS."""
        if not getattr(s, "findings_by_category", None):
            return ""
        icons = {
            "iam": "👤", "s3": "🪣", "network": "🌐", "rds": "🗄️",
            "cloudfront": "🚀", "logging": "📜", "ec2": "🖥️",
            "lambda": "⚡", "storage": "💾", "dynamodb": "📊", "tagging": "🏷️",
        }
        cats = "".join(
            f'<div style="background:#f8fafc;border:1px solid #e8edf3;border-radius:10px;'
            f'padding:10px 14px;font-size:12px;color:#334155;">'
            f'{icons.get(cat, "🔧")} {cat.upper()} <b style="color:#0f172a;">{n}</b></div>'
            for cat, n in s.findings_by_category.items()
        )
        return (
            f'<div class="card" style="background:#fff;border-radius:14px;padding:28px;'
            f'margin-bottom:24px;border:1px solid #e8edf3;">'
            f'<h2 class="section-title" style="margin:0 0 4px;font-size:19px;color:#0f172a;">'
            f'🗂️ Hallazgos por Servicio</h2>'
            f'<p class="section-sub" style="margin:0 0 20px;color:#64748b;font-size:13px;">'
            f'Distribución por categoría de recurso AWS</p>'
            f'<div class="cat-grid" style="display:flex;flex-wrap:wrap;gap:10px;">{cats}</div></div>'
        )

    def _top5_section(self, findings: List[Finding]) -> str:
        max_saving = max((f.potential_saving for f in findings), default=1) or 1
        rows = ""
        for i, f in enumerate(findings, 1):
            pct = (f.potential_saving / max_saving) * 100
            rows += (
                f'<tr>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;font-weight:700;color:#94a3b8;">#{i}</td>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;">'
                f'<strong>{f.title}</strong><br>'
                f'<span style="color:#64748b;font-size:11px;font-family:Consolas,monospace;">{f.resource_id}</span></td>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;width:230px;">'
                f'<span style="color:#059669;font-weight:700;">${f.potential_saving:,.2f}/mes</span>'
                f'<div style="background:#ecfdf5;border-radius:6px;height:8px;margin-top:5px;overflow:hidden;">'
                f'<span style="display:block;height:100%;width:{pct:.0f}%;background:#059669;"></span></div>'
                f'</td></tr>'
            )
        return (
            f'<div class="card" style="background:#fff;border-radius:14px;padding:28px;'
            f'margin-bottom:24px;border:1px solid #e8edf3;">'
            f'<h2 class="section-title" style="margin:0 0 4px;font-size:19px;color:#0f172a;">'
            f'💡 Top 5 Oportunidades de Ahorro</h2>'
            f'<p class="section-sub" style="margin:0 0 20px;color:#64748b;font-size:13px;">'
            f'Los recursos con mayor ahorro potencial mensual</p>'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px;"><thead><tr>'
            f'<th style="width:40px;padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">#</th>'
            f'<th style="padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Hallazgo / Recurso</th>'
            f'<th style="padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Ahorro potencial</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>'
        )

    def _domain_section(self, title: str, findings: List[Finding], accent: str) -> str:
        rows = ""
        for f in findings:
            sev_color = SEVERITY_COLORS.get(f.severity, "#475569")
            sev_bg    = SEVERITY_BG.get(f.severity, "#f1f5f9")
            cost_cell = (
                f'<span style="color:#059669;font-weight:700;">${f.potential_saving:,.2f}/mes</span>'
                if f.potential_saving > 0 else '<span style="color:#cbd5e1;">—</span>'
            )
            owner_cell = (
                f'<span style="background:#eef2ff;color:#4338ca;padding:2px 8px;'
                f'border-radius:6px;font-size:11px;">{f.owner}</span>'
                if f.owner and f.owner != "unknown"
                else '<span style="color:#cbd5e1;font-size:11px;">sin owner</span>'
            )
            rows += (
                f'<tr>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;">'
                f'<span style="background:{sev_bg};color:{sev_color};padding:3px 10px;'
                f'border-radius:999px;font-size:10.5px;font-weight:800;">{f.severity.upper()}</span></td>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;">'
                f'<strong>{f.title}</strong><br>'
                f'<span style="color:#64748b;font-size:11px;font-family:Consolas,monospace;">{f.resource_id}</span></td>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;font-size:12px;color:#475569;">'
                f'{f.recommendation[:140]}</td>'
                f'<td class="hide-mobile" style="padding:12px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;">{owner_cell}</td>'
                f'<td style="padding:12px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;">{cost_cell}</td>'
                f'</tr>'
            )
        return (
            f'<div class="card" style="background:#fff;border-radius:14px;padding:28px;'
            f'margin-bottom:24px;border:1px solid #e8edf3;border-top:4px solid {accent};">'
            f'<h2 class="section-title" style="margin:0 0 4px;font-size:19px;color:#0f172a;">{title}</h2>'
            f'<p class="section-sub" style="margin:0 0 20px;color:#64748b;font-size:13px;">'
            f'{len(findings)} hallazgo(s) detectado(s)</p>'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px;"><thead><tr>'
            f'<th style="width:90px;padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Severidad</th>'
            f'<th style="padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Hallazgo / Recurso</th>'
            f'<th style="padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Recomendación</th>'
            f'<th class="hide-mobile" style="width:130px;padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Owner</th>'
            f'<th style="width:110px;padding:10px;border-bottom:2px solid #e2e8f0;background:#f8fafc;text-align:left;">Ahorro</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>'
        )
