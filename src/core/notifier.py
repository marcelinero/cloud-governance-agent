"""
notifier.py — Enruta y envía notificaciones por email via Amazon SES.

Estrategia de enrutamiento:
  - Auditoría:  reporte HTML completo
  - FinOps:     solo hallazgos de dominio 'finops'
  - Seguridad:  solo hallazgos de dominio 'security'
  - Owner:      hallazgos donde finding.owner es un email válido
"""

from __future__ import annotations

import email.mime.base
import email.mime.multipart
import email.mime.text
import os
import re
from typing import Dict, List, Optional

from src.core.models import Finding, Report
from src.core.report_generator import ReportGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class Notifier:
    """Envía reportes segmentados por rol a los destinatarios configurados."""

    def __init__(self, ses_client=None) -> None:
        import boto3
        self.ses          = ses_client or boto3.client("ses")
        self.sender       = os.environ.get("SES_SENDER_EMAIL", "")
        self.audit_email  = os.environ.get("AUDIT_EMAIL", "")
        self.finops_email = os.environ.get("FINOPS_EMAIL", "")
        self.sec_email    = os.environ.get("SECURITY_EMAIL", "")

    def notify(self, report: Report, html_content: str, s3_key: str) -> Dict[str, int]:
        """
        Envía los emails segmentados según el rol del destinatario.

        Args:
            report:       Reporte completo del CGA.
            html_content: Reporte HTML completo generado por ReportGenerator.
            s3_key:       Clave S3 del reporte JSON para referencia.

        Returns:
            Dict[str, int]: Conteo de emails enviados por categoría.
        """
        if not self.sender:
            logger.warning("SES_SENDER_EMAIL no configurado — omitiendo notificaciones")
            return {}

        sent: Dict[str, int] = {"audit": 0, "finops": 0, "security": 0, "owner": 0}
        subject_prefix = f"[CGA] {report.account_name} — {report.generated_at[:10]}"

        # 1. Auditoría — reporte completo
        if self.audit_email and self._valid_email(self.audit_email):
            subject = (
                f"{subject_prefix} — "
                f"{report.summary.total_findings} hallazgos | "
                f"Ahorro potencial: ${report.summary.total_potential_saving:,.2f}/mes"
            )
            if self._send(self.audit_email, subject, html_content, report.report_id):
                sent["audit"] += 1

        # 2. FinOps — solo hallazgos de costos
        if self.finops_email and self._valid_email(self.finops_email):
            finops_findings = [f for f in report.findings if f.domain == "finops"]
            if finops_findings:
                saving = sum(f.potential_saving for f in finops_findings)
                subj   = (
                    f"{subject_prefix} — FinOps: {len(finops_findings)} hallazgos | "
                    f"Ahorro potencial: ${saving:,.2f}/mes"
                )
                html_finops = self._generate_partial_html(
                    report, finops_findings, "💰 Reporte FinOps — Optimización de Costos"
                )
                if self._send(self.finops_email, subj, html_finops, report.report_id):
                    sent["finops"] += 1

        # 3. Seguridad — solo hallazgos de seguridad
        if self.sec_email and self._valid_email(self.sec_email):
            sec_findings = [f for f in report.findings if f.domain == "security"]
            if sec_findings:
                critical = sum(1 for f in sec_findings if f.severity == "critical")
                subj     = (
                    f"{subject_prefix} — Seguridad: {len(sec_findings)} hallazgos "
                    f"({critical} críticos)"
                )
                html_sec = self._generate_partial_html(
                    report, sec_findings, "🔐 Reporte de Seguridad"
                )
                if self._send(self.sec_email, subj, html_sec, report.report_id):
                    sent["security"] += 1

        # 4. Owners individuales — sus propios recursos
        owner_map: Dict[str, List[Finding]] = {}
        for f in report.findings:
            if self._valid_email(f.owner):
                owner_map.setdefault(f.owner, []).append(f)

        for owner_email, owner_findings in owner_map.items():
            if owner_email in (self.audit_email, self.finops_email, self.sec_email):
                continue  # Ya recibió el reporte completo o de su dominio
            subj = (
                f"{subject_prefix} — Sus recursos: {len(owner_findings)} hallazgos"
            )
            html_owner = self._generate_partial_html(
                report, owner_findings,
                f"🔔 Hallazgos de sus recursos — {owner_email}"
            )
            if self._send(owner_email, subj, html_owner, report.report_id):
                sent["owner"] += 1

        logger.info("Notificaciones enviadas", extra={"sent": sent})
        return sent

    # ------------------------------------------------------------------
    # Generador de HTML parcial (por rol)
    # ------------------------------------------------------------------
    def _generate_partial_html(
        self, report: Report, findings: List[Finding], title: str
    ) -> str:
        """Genera un HTML simplificado con solo los hallazgos relevantes para el rol."""
        gen = ReportGenerator.__new__(ReportGenerator)
        # Construir tabla de hallazgos
        rows = ""
        for f in findings:
            from src.core.report_generator import SEVERITY_COLORS, SEVERITY_BG
            sev_color = SEVERITY_COLORS.get(f.severity, "#475569")
            sev_bg    = SEVERITY_BG.get(f.severity, "#f1f5f9")
            cost_cell = (
                f'<span style="color:#059669;">${f.potential_saving:,.2f}/mes</span>'
                if f.potential_saving > 0 else "—"
            )
            rows += (
                f'<tr>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;">'
                f'<span style="background:{sev_bg};color:{sev_color};padding:2px 8px;'
                f'border-radius:12px;font-size:11px;font-weight:bold;">'
                f'{f.severity.upper()}</span></td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;">'
                f'<strong>{f.title}</strong><br>'
                f'<span style="color:#64748b;font-size:11px;">{f.resource_id}</span></td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;font-size:12px;">'
                f'{f.recommendation[:150]}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #f1f5f9;">{cost_cell}</td>'
                f'</tr>'
            )

        total_saving = sum(f.potential_saving for f in findings)
        return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;padding:20px;color:#1e293b;">
<div style="background:#1e293b;color:#fff;padding:20px;border-radius:8px;margin-bottom:20px;">
  <h1 style="margin:0;font-size:20px;">{title}</h1>
  <p style="margin:6px 0 0;color:#94a3b8;font-size:13px;">
    {report.account_name} | {report.generated_at[:10]} |
    {len(findings)} hallazgo(s)
    {f'| Ahorro potencial: ${total_saving:,.2f}/mes' if total_saving > 0 else ''}
  </p>
</div>
<div style="background:#fff;border-radius:8px;padding:20px;border:1px solid #e2e8f0;">
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:#f8fafc;">
        <th style="padding:8px;text-align:left;color:#475569;width:90px;">Severidad</th>
        <th style="padding:8px;text-align:left;color:#475569;">Hallazgo</th>
        <th style="padding:8px;text-align:left;color:#475569;">Recomendación</th>
        <th style="padding:8px;text-align:left;color:#475569;width:100px;">Ahorro</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<p style="text-align:center;color:#94a3b8;font-size:11px;margin-top:16px;">
  Cloud Governance Agent | Reporte ID: {report.report_id}
</p>
</body></html>"""

    # ------------------------------------------------------------------
    # Envío via SES
    # ------------------------------------------------------------------
    def _send(
        self, to: str, subject: str, html_body: str, report_id: str
    ) -> bool:
        """
        Envía un email via Amazon SES con el cuerpo HTML.

        Args:
            to:        Dirección de destino.
            subject:   Asunto del email.
            html_body: Contenido HTML del email.
            report_id: ID del reporte para logging.

        Returns:
            bool: True si el envío fue exitoso.
        """
        try:
            msg = email.mime.multipart.MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.sender
            msg["To"]      = to

            # Texto plano como fallback
            plain = "Este reporte requiere un cliente de email con soporte HTML."
            msg.attach(email.mime.text.MIMEText(plain, "plain", "utf-8"))
            msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

            self.ses.send_raw_email(
                Source=self.sender,
                Destinations=[to],
                RawMessage={"Data": msg.as_string()},
            )
            logger.info("Email enviado", extra={"to": to, "subject": subject[:60]})
            return True

        except Exception as e:
            logger.error("Error enviando email",
                         extra={"to": to, "report_id": report_id, "error": str(e)})
            return False

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    @staticmethod
    def _valid_email(email_str: str) -> bool:
        return bool(email_str and EMAIL_RE.match(email_str.strip()))
