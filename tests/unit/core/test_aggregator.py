"""Tests unitarios del Aggregator."""

from src.core.aggregator import Aggregator
from src.core.models import Finding


def _finding(resource_id, category, severity, title, saving=0.0):
    return Finding(
        domain="finops" if category in ("ec2", "s3") else "security",
        category=category, severity=severity,
        resource_id=resource_id, resource_type="AWS::Test",
        region="us-east-1", account_id="123456789012",
        title=title, description="desc", recommendation="rec",
        potential_saving=saving,
    )


def test_deduplica_por_resource_category_title():
    findings = [
        _finding("i-1", "ec2", "high", "CPU baja", 45.0),
        _finding("i-1", "ec2", "high", "CPU baja", 45.0),  # duplicado exacto
    ]
    agg = Aggregator()
    result, summary = agg.aggregate(findings)
    assert len(result) == 1
    assert summary.total_findings == 1


def test_conserva_mayor_severidad_en_duplicados():
    findings = [
        _finding("i-1", "ec2", "medium", "Problema X"),
        _finding("i-1", "ec2", "critical", "Problema X"),  # misma clave, más grave
    ]
    agg = Aggregator()
    result, _ = agg.aggregate(findings)
    assert len(result) == 1
    assert result[0].severity == "critical"


def test_ordena_por_severidad_critical_primero():
    findings = [
        _finding("i-3", "s3", "low", "Low issue"),
        _finding("i-1", "iam", "critical", "Critical issue"),
        _finding("i-2", "ec2", "medium", "Medium issue"),
    ]
    agg = Aggregator()
    result, _ = agg.aggregate(findings)
    severities = [f.severity for f in result]
    assert severities == ["critical", "medium", "low"]


def test_summary_suma_ahorro_total():
    findings = [
        _finding("i-1", "ec2", "high", "A", 10.0),
        _finding("i-2", "ec2", "high", "B", 25.5),
    ]
    agg = Aggregator()
    _, summary = agg.aggregate(findings)
    assert summary.total_potential_saving == 35.5
