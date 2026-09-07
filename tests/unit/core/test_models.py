"""Tests unitarios de los modelos de datos (models.py)."""

from src.core.models import Finding, Report, ReportSummary


def _finding(**overrides):
    base = dict(
        domain="security", category="iam", severity="critical",
        resource_id="arn:test", resource_type="AWS::IAM::User",
        region="global", account_id="123456789012",
        title="Test", description="desc", recommendation="rec",
    )
    base.update(overrides)
    return Finding(**base)


def test_finding_genera_uuid_y_timestamp():
    f = _finding()
    assert f.id
    assert f.timestamp
    assert f.owner == "unknown"


def test_severity_order():
    assert _finding(severity="critical").severity_order() == 0
    assert _finding(severity="high").severity_order() == 1
    assert _finding(severity="medium").severity_order() == 2
    assert _finding(severity="low").severity_order() == 3


def test_finding_to_dict_y_from_dict_roundtrip():
    f = _finding(potential_saving=45.5, estimated_monthly_cost=60.0)
    d = f.to_dict()
    f2 = Finding.from_dict(d)
    assert f2.resource_id == f.resource_id
    assert f2.severity == f.severity
    assert f2.potential_saving == 45.5


def test_report_summary_from_findings_cuenta_severidades():
    findings = [
        _finding(severity="critical"),
        _finding(severity="high", potential_saving=10.0),
        _finding(severity="high", potential_saving=20.0),
        _finding(severity="medium"),
    ]
    summary = ReportSummary.from_findings(findings)
    assert summary.total_findings == 4
    assert summary.critical == 1
    assert summary.high == 2
    assert summary.medium == 1
    assert summary.total_potential_saving == 30.0


def test_report_to_dict_incluye_findings_y_summary():
    findings = [_finding()]
    summary = ReportSummary.from_findings(findings)
    report = Report(
        account_id="123456789012", account_name="Test",
        region="us-east-1", execution_type="on-demand",
        summary=summary, findings=findings,
    )
    d = report.to_dict()
    assert d["account_id"] == "123456789012"
    assert len(d["findings"]) == 1
    assert d["summary"]["total_findings"] == 1
