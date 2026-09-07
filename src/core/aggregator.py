"""
aggregator.py — Consolida, deduplica y ordena hallazgos del CGA.

Responsabilidades:
  1. Recibir hallazgos de todos los checkers
  2. Deduplicar por (resource_id, category)
  3. Ordenar por severidad: critical → high → medium → low
  4. Construir ReportSummary con totales y agrupaciones
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from src.core.models import Finding, ReportSummary
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Aggregator:
    """Consolida hallazgos de múltiples checkers en un conjunto deduplicado y ordenado."""

    def aggregate(self, all_findings: List[Finding]) -> Tuple[List[Finding], ReportSummary]:
        """
        Recibe todos los hallazgos crudos, los procesa y retorna la lista final.

        Args:
            all_findings: Lista combinada de hallazgos de todos los checkers.

        Returns:
            Tuple[List[Finding], ReportSummary]:
              - Lista deduplicada y ordenada de hallazgos
              - Resumen ejecutivo construido a partir de los hallazgos finales
        """
        logger.info("Iniciando agregación", extra={"total_raw": len(all_findings)})

        deduplicated = self._deduplicate(all_findings)
        sorted_findings = self._sort_by_severity(deduplicated)
        summary = ReportSummary.from_findings(sorted_findings)

        logger.info(
            "Agregación completada",
            extra={
                "raw":    len(all_findings),
                "final":  len(sorted_findings),
                "dupes_removed": len(all_findings) - len(sorted_findings),
                "critical": summary.critical,
                "high":     summary.high,
                "medium":   summary.medium,
                "low":      summary.low,
                "potential_saving_usd": summary.total_potential_saving,
            },
        )
        return sorted_findings, summary

    # ------------------------------------------------------------------
    # Deduplicación
    # ------------------------------------------------------------------
    def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
        """
        Elimina hallazgos duplicados basándose en (resource_id, category, title).

        Cuando hay duplicados, conserva el de mayor severidad.

        Args:
            findings: Lista con posibles duplicados.

        Returns:
            Lista sin duplicados.
        """
        seen: Dict[Tuple[str, str, str], Finding] = {}

        for finding in findings:
            key = (finding.resource_id, finding.category, finding.title)
            if key not in seen:
                seen[key] = finding
            else:
                # Conservar el de mayor severidad (menor número = más grave)
                existing = seen[key]
                if finding.severity_order() < existing.severity_order():
                    seen[key] = finding

        return list(seen.values())

    # ------------------------------------------------------------------
    # Ordenamiento por severidad
    # ------------------------------------------------------------------
    def _sort_by_severity(self, findings: List[Finding]) -> List[Finding]:
        """
        Ordena hallazgos por severidad (critical primero) y luego por dominio.

        Args:
            findings: Lista de hallazgos deduplicados.

        Returns:
            Lista ordenada.
        """
        domain_order = {"security": 0, "finops": 1, "compliance": 2}
        return sorted(
            findings,
            key=lambda f: (f.severity_order(), domain_order.get(f.domain, 9), f.resource_id),
        )
