"""Tests unitarios del ReportGenerator (generación HTML, sin S3)."""

from src.core.models import Finding, Report, ReportSummary
from src.core.report_generator import ReportGenerator


def _report():
    findings = [
        Finding(
            domain="security", category="iam", severity="critical",
            resource_id="arn:aws:iam::123456789012:user/admin",
            resource_type="AWS::IAM::User", region="global",
            account_id="123456789012", title="Usuario sin MFA",
            description="desc", recommendation="Habilitar MFA",
            owner="admin@empresa.com",
        ),
        Finding(
            domain="finops", category="ec2", severity="high",
            resource_id="i-123", resource_type="AWS::EC2::Instance",
            region="us-east-1", account_id="123456789012",
            title="EC2 subutilizada", description="desc",
            recommendation="Rightsizing", potential_saving=45.0,
            estimated_monthly_cost=60.0,
        ),
    ]
    summary = ReportSummary.from_findings(findings)
    return Report(
        account_id="123456789012", account_name="ACME Corp",
        region="us-east-1", execution_type="on-demand",
        summary=summary, findings=findings, duration_seconds=5.2,
    )


def test_html_contiene_elementos_clave():
    gen = ReportGenerator.__new__(ReportGenerator)  # sin init S3
    html = gen._generate_html(_report())
    assert "<html" in html
    assert "ACME Corp" in html
    assert "Cloud Governance Agent" in html
    assert "Usuario sin MFA" in html
    assert "EC2 subutilizada" in html


def test_html_muestra_resumen_ejecutivo():
    gen = ReportGenerator.__new__(ReportGenerator)
    html = gen._generate_html(_report())
    # Debe mostrar el resumen con totales y ahorro
    assert "Resumen Ejecutivo" in html
    assert "Ahorro Potencial" in html


def test_html_seccion_top_ahorros_cuando_hay_saving():
    gen = ReportGenerator.__new__(ReportGenerator)
    html = gen._generate_html(_report())
    assert "Top 5 Oportunidades de Ahorro" in html
