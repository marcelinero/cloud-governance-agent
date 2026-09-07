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
    assert "Ahorro potencial" in html


def test_html_seccion_top_ahorros_cuando_hay_saving():
    gen = ReportGenerator.__new__(ReportGenerator)
    html = gen._generate_html(_report())
    assert "Top 5 Oportunidades de Ahorro" in html


def test_html_incluye_elementos_enriquecidos():
    """El HTML mejorado debe incluir hero, barra de severidad y sección de servicios."""
    gen = ReportGenerator.__new__(ReportGenerator)
    html = gen._generate_html(_report())
    assert "<style>" in html                      # estilos avanzados para navegador
    assert 'class="hero"' in html                 # header con gradiente
    assert "Hallazgos por Servicio" in html       # sección de categorías
    assert "linear-gradient" in html              # gradiente del hero
    assert "@media" in html                        # responsive


import boto3
from moto import mock_aws


@mock_aws
def test_generate_sube_json_y_html_a_s3_con_fecha():
    """generate() debe subir tanto el JSON como el HTML a S3 con nombre fechado."""
    bucket = "cga-reports-test"
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)

    gen = ReportGenerator(s3_client=s3, bucket_name=bucket)
    json_key, html_key, html_str = gen.generate(_report())

    # Ambas claves incluyen el prefijo de fecha y el nombre cga-report-
    assert json_key.endswith(".json")
    assert html_key.endswith(".html")
    assert "cga-report-" in json_key
    assert "cga-report-" in html_key
    # JSON y HTML comparten el mismo nombre base (solo cambia la extensión)
    assert json_key[:-5] == html_key[:-5]

    # Los objetos existen en S3 con el content-type correcto
    objs = s3.list_objects_v2(Bucket=bucket)["Contents"]
    keys = {o["Key"] for o in objs}
    assert json_key in keys
    assert html_key in keys

    html_obj = s3.get_object(Bucket=bucket, Key=html_key)
    assert html_obj["ContentType"].startswith("text/html")
    assert "ACME Corp" in html_str
