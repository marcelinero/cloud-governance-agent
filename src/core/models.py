"""
models.py — Modelos de datos centrales del Cloud Governance Agent (CGA).

Define las estructuras Finding, ReportSummary y Report usando dataclasses
con validación de literales para dominio, categoría y severidad.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

# ---------------------------------------------------------------------------
# Literales de dominio, severidad y categoría
# ---------------------------------------------------------------------------

Domain   = Literal["security", "finops", "compliance"]
Severity = Literal["critical", "high", "medium", "low"]
Category = Literal[
    "iam", "s3", "network", "rds", "cloudfront",
    "logging", "ec2", "lambda", "storage", "dynamodb",
    "ecs", "tagging",
]

# Orden numérico para ordenar por severidad (menor = más grave)
SEVERITY_ORDER: Dict[str, int] = {
    "critical": 0,
    "high":     1,
    "medium":   2,
    "low":      3,
}


# ---------------------------------------------------------------------------
# Finding — Hallazgo individual de auditoría
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """
    Representa un hallazgo de auditoría sobre un recurso AWS.

    Attributes:
        id:                    UUID v4 único del hallazgo.
        domain:                Dominio de auditoría: security | finops | compliance.
        category:              Categoría del servicio AWS auditado.
        severity:              Nivel de severidad: critical | high | medium | low.
        resource_id:           ARN o ID del recurso afectado.
        resource_type:         Tipo CloudFormation del recurso (e.g. AWS::EC2::Instance).
        region:                Región AWS del recurso (o "global" para IAM/CloudFront).
        account_id:            ID de la cuenta AWS.
        title:                 Título corto y descriptivo del hallazgo.
        description:           Descripción detallada del problema encontrado.
        recommendation:        Acción recomendada para resolver el hallazgo.
        owner:                 Valor del tag Owner del recurso (email o nombre).
        project:               Valor del tag Project del recurso.
        environment:           Valor del tag Environment del recurso.
        cost_center:           Valor del tag CostCenter del recurso.
        estimated_monthly_cost: Costo mensual estimado del recurso en USD.
        potential_saving:      Ahorro potencial mensual en USD si se resuelve.
        timestamp:             Momento del hallazgo en formato ISO 8601 UTC.
        evidence:              Datos crudos del recurso tal como los retorna la API AWS.
    """

    # Campos obligatorios
    domain:        Domain
    category:      Category
    severity:      Severity
    resource_id:   str
    resource_type: str
    region:        str
    account_id:    str
    title:         str
    description:   str
    recommendation: str

    # Campos opcionales — extraídos de tags del recurso
    owner:       str = "unknown"
    project:     str = "unknown"
    environment: str = "unknown"
    cost_center: str = "unknown"

    # Campos financieros — aplican principalmente a hallazgos FinOps
    estimated_monthly_cost: float = 0.0
    potential_saving:       float = 0.0

    # Metadatos
    id:        str  = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str  = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence:  dict = field(default_factory=dict)

    def severity_order(self) -> int:
        """Retorna el orden numérico de severidad para ordenamiento. Menor = más grave."""
        return SEVERITY_ORDER.get(self.severity, 99)

    def to_dict(self) -> dict:
        """Serializa el Finding a un diccionario JSON-serializable."""
        return {
            "id":                     self.id,
            "domain":                 self.domain,
            "category":               self.category,
            "severity":               self.severity,
            "resource_id":            self.resource_id,
            "resource_type":          self.resource_type,
            "region":                 self.region,
            "account_id":             self.account_id,
            "title":                  self.title,
            "description":            self.description,
            "recommendation":         self.recommendation,
            "owner":                  self.owner,
            "project":                self.project,
            "environment":            self.environment,
            "cost_center":            self.cost_center,
            "estimated_monthly_cost": round(self.estimated_monthly_cost, 2),
            "potential_saving":       round(self.potential_saving, 2),
            "timestamp":              self.timestamp,
            "evidence":               self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        """Deserializa un Finding desde un diccionario."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            domain=data["domain"],
            category=data["category"],
            severity=data["severity"],
            resource_id=data["resource_id"],
            resource_type=data["resource_type"],
            region=data["region"],
            account_id=data["account_id"],
            title=data["title"],
            description=data["description"],
            recommendation=data["recommendation"],
            owner=data.get("owner", "unknown"),
            project=data.get("project", "unknown"),
            environment=data.get("environment", "unknown"),
            cost_center=data.get("cost_center", "unknown"),
            estimated_monthly_cost=data.get("estimated_monthly_cost", 0.0),
            potential_saving=data.get("potential_saving", 0.0),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            evidence=data.get("evidence", {}),
        )


# ---------------------------------------------------------------------------
# ReportSummary — Resumen ejecutivo del reporte
# ---------------------------------------------------------------------------

@dataclass
class ReportSummary:
    """
    Resumen ejecutivo con totales y métricas agregadas del reporte.

    Attributes:
        total_findings:         Número total de hallazgos.
        critical:               Hallazgos de severidad critical.
        high:                   Hallazgos de severidad high.
        medium:                 Hallazgos de severidad medium.
        low:                    Hallazgos de severidad low.
        total_estimated_cost:   Costo mensual total estimado de recursos con hallazgos (USD).
        total_potential_saving: Ahorro potencial total mensual (USD).
        findings_by_domain:     Conteo de hallazgos agrupados por dominio.
        findings_by_owner:      Conteo de hallazgos agrupados por Owner tag.
        findings_by_category:   Conteo de hallazgos agrupados por categoría de servicio.
    """

    total_findings:         int   = 0
    critical:               int   = 0
    high:                   int   = 0
    medium:                 int   = 0
    low:                    int   = 0
    total_estimated_cost:   float = 0.0
    total_potential_saving: float = 0.0
    findings_by_domain:     Dict[str, int] = field(default_factory=dict)
    findings_by_owner:      Dict[str, int] = field(default_factory=dict)
    findings_by_category:   Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serializa el ReportSummary a un diccionario JSON-serializable."""
        return {
            "total_findings":          self.total_findings,
            "critical":                self.critical,
            "high":                    self.high,
            "medium":                  self.medium,
            "low":                     self.low,
            "total_estimated_cost":    round(self.total_estimated_cost, 2),
            "total_potential_saving":  round(self.total_potential_saving, 2),
            "findings_by_domain":      self.findings_by_domain,
            "findings_by_owner":       self.findings_by_owner,
            "findings_by_category":    self.findings_by_category,
        }

    @classmethod
    def from_findings(cls, findings: List[Finding]) -> "ReportSummary":
        """Construye un ReportSummary a partir de una lista de Finding."""
        summary = cls()
        summary.total_findings = len(findings)

        by_domain:   Dict[str, int] = {}
        by_owner:    Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for f in findings:
            # Conteo por severidad
            if f.severity == "critical":
                summary.critical += 1
            elif f.severity == "high":
                summary.high += 1
            elif f.severity == "medium":
                summary.medium += 1
            elif f.severity == "low":
                summary.low += 1

            # Acumulados financieros
            summary.total_estimated_cost   += f.estimated_monthly_cost
            summary.total_potential_saving += f.potential_saving

            # Agrupaciones
            by_domain[f.domain]       = by_domain.get(f.domain, 0) + 1
            by_owner[f.owner]         = by_owner.get(f.owner, 0) + 1
            by_category[f.category]   = by_category.get(f.category, 0) + 1

        summary.findings_by_domain   = dict(sorted(by_domain.items(),   key=lambda x: x[1], reverse=True))
        summary.findings_by_owner    = dict(sorted(by_owner.items(),     key=lambda x: x[1], reverse=True))
        summary.findings_by_category = dict(sorted(by_category.items(),  key=lambda x: x[1], reverse=True))

        summary.total_estimated_cost   = round(summary.total_estimated_cost,   2)
        summary.total_potential_saving = round(summary.total_potential_saving, 2)

        return summary


# ---------------------------------------------------------------------------
# Report — Reporte completo de auditoría
# ---------------------------------------------------------------------------

@dataclass
class Report:
    """
    Reporte completo de una ejecución del Cloud Governance Agent.

    Attributes:
        report_id:      UUID v4 único del reporte.
        account_id:     ID de la cuenta AWS auditada.
        account_name:   Nombre descriptivo de la cuenta.
        region:         Región principal de auditoría.
        generated_at:   Timestamp de generación en ISO 8601 UTC.
        execution_type: Tipo de ejecución: scheduled | on-demand.
        duration_seconds: Duración total de la ejecución en segundos.
        summary:        Resumen ejecutivo con totales y métricas.
        findings:       Lista completa de hallazgos ordenados por severidad.
    """

    account_id:       str
    account_name:     str
    region:           str
    execution_type:   Literal["scheduled", "on-demand"]
    summary:          ReportSummary
    findings:         List[Finding]

    report_id:        str   = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at:     str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Serializa el Report completo a un diccionario JSON-serializable."""
        return {
            "report_id":        self.report_id,
            "account_id":       self.account_id,
            "account_name":     self.account_name,
            "region":           self.region,
            "generated_at":     self.generated_at,
            "execution_type":   self.execution_type,
            "duration_seconds": round(self.duration_seconds, 2),
            "summary":          self.summary.to_dict(),
            "findings":         [f.to_dict() for f in self.findings],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        """Deserializa un Report desde un diccionario."""
        findings = [Finding.from_dict(f) for f in data.get("findings", [])]
        summary  = ReportSummary(**data["summary"]) if isinstance(data.get("summary"), dict) else ReportSummary()
        return cls(
            report_id=data.get("report_id", str(uuid.uuid4())),
            account_id=data["account_id"],
            account_name=data["account_name"],
            region=data["region"],
            generated_at=data.get("generated_at", datetime.now(timezone.utc).isoformat()),
            execution_type=data.get("execution_type", "on-demand"),
            duration_seconds=data.get("duration_seconds", 0.0),
            summary=summary,
            findings=findings,
        )
