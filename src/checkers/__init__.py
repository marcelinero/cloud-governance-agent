"""
checkers/__init__.py — Interfaz base para todos los checkers del CGA.

Define BaseChecker como clase abstracta que todos los checkers deben
implementar. Garantiza una interfaz uniforme para el orquestador.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.models import Category, Domain, Finding, Severity
from src.utils.aws_client import AWSClientFactory
from src.utils.logger import get_logger


class BaseChecker(ABC):
    """
    Clase abstracta base para todos los checkers del Cloud Governance Agent.

    Cada checker concreto debe:
      1. Heredar de BaseChecker
      2. Implementar el método run() que retorna List[Finding]
      3. Llamar a _build_finding() para construir hallazgos de forma consistente

    Attributes:
        factory:    AWSClientFactory para acceder a clientes boto3.
        config:     Diccionario con configuración y umbrales del agente.
        account_id: ID de la cuenta AWS auditada.
        region:     Región principal de auditoría.
        logger:     Logger JSON estructurado para el checker.
    """

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        """
        Inicializa el checker con el factory de clientes y la configuración.

        Args:
            factory: AWSClientFactory instanciado con la región correcta.
            config:  Diccionario de configuración con keys:
                       - account_id (str)
                       - region (str)
                       - cpu_threshold_percent (int)
                       - stopped_days_threshold (int)
                       - key_age_days_threshold (int)
        """
        self.factory    = factory
        self.config     = config
        self.account_id = config.get("account_id", "unknown")
        self.region     = config.get("region", "us-east-1")
        self.logger     = get_logger(self.__class__.__name__)

    @abstractmethod
    def run(self) -> List[Finding]:
        """
        Ejecuta todos los checks del módulo y retorna los hallazgos.

        Returns:
            List[Finding]: Lista de hallazgos encontrados.
                           Lista vacía si todos los recursos están conformes.

        Raises:
            Exception: Los checkers deben capturar sus propias excepciones
                       y registrarlas como WARNING para no interrumpir el
                       flujo del orquestador.
        """

    def _build_finding(
        self,
        domain:        Domain,
        category:      Category,
        severity:      Severity,
        resource_id:   str,
        resource_type: str,
        title:         str,
        description:   str,
        recommendation: str,
        region:        Optional[str] = None,
        owner:         str = "unknown",
        project:       str = "unknown",
        environment:   str = "unknown",
        cost_center:   str = "unknown",
        estimated_monthly_cost: float = 0.0,
        potential_saving:       float = 0.0,
        evidence:      Optional[Dict[str, Any]] = None,
    ) -> Finding:
        """
        Construye un Finding con valores por defecto para campos opcionales.

        Args:
            domain:                 Dominio de auditoría.
            category:               Categoría del servicio AWS.
            severity:               Nivel de severidad.
            resource_id:            ARN o ID del recurso.
            resource_type:          Tipo CloudFormation del recurso.
            title:                  Título corto del hallazgo.
            description:            Descripción detallada.
            recommendation:         Acción recomendada.
            region:                 Región del recurso (usa self.region si no se especifica).
            owner:                  Valor del tag Owner.
            project:                Valor del tag Project.
            environment:            Valor del tag Environment.
            cost_center:            Valor del tag CostCenter.
            estimated_monthly_cost: Costo mensual estimado en USD.
            potential_saving:       Ahorro potencial mensual en USD.
            evidence:               Datos crudos del recurso.

        Returns:
            Finding: Objeto Finding completamente construido.
        """
        return Finding(
            domain=domain,
            category=category,
            severity=severity,
            resource_id=resource_id,
            resource_type=resource_type,
            region=region or self.region,
            account_id=self.account_id,
            title=title,
            description=description,
            recommendation=recommendation,
            owner=owner,
            project=project,
            environment=environment,
            cost_center=cost_center,
            estimated_monthly_cost=estimated_monthly_cost,
            potential_saving=potential_saving,
            evidence=evidence or {},
        )

    def _extract_tags(self, tags: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Convierte la lista de tags AWS [{Key: ..., Value: ...}]
        en un diccionario plano {key_lower: value}.

        Args:
            tags: Lista de dicts con claves "Key" y "Value" (formato AWS API).

        Returns:
            Dict[str, str]: Tags como diccionario con claves en minúsculas.
        """
        if not tags:
            return {}
        return {t.get("Key", "").lower(): t.get("Value", "") for t in tags}

    def _get_tag(self, tags: Dict[str, str], key: str, default: str = "unknown") -> str:
        """
        Obtiene el valor de un tag por nombre (case-insensitive).

        Args:
            tags:    Diccionario de tags ya procesado con _extract_tags.
            key:     Nombre del tag a buscar.
            default: Valor por defecto si el tag no existe.

        Returns:
            str: Valor del tag o default si no existe.
        """
        return tags.get(key.lower(), default) or default

    def _check_required_tags(
        self,
        resource_id:   str,
        resource_type: str,
        tags:          Dict[str, str],
        required_tags: Optional[List[str]] = None,
    ) -> List[Finding]:
        """
        Verifica que un recurso tenga todos los tags obligatorios.

        Genera un Finding de severidad MEDIUM por cada tag ausente.

        Args:
            resource_id:   ARN o ID del recurso.
            resource_type: Tipo CloudFormation del recurso.
            tags:          Tags ya procesados con _extract_tags.
            required_tags: Lista de tags obligatorios a verificar.
                           Por defecto: ["owner", "project", "environment", "costcenter"].

        Returns:
            List[Finding]: Un Finding por cada tag ausente.
        """
        if required_tags is None:
            required_tags = ["owner", "project", "environment", "costcenter"]

        findings = []
        # Normalizar nombres de tags para comparación
        tag_map = {
            "owner":       "Owner",
            "project":     "Project",
            "environment": "Environment",
            "costcenter":  "CostCenter",
        }

        for tag_key in required_tags:
            normalized = tag_key.lower().replace("-", "").replace("_", "")
            display    = tag_map.get(normalized, tag_key)

            if not tags.get(normalized) and not tags.get(tag_key.lower()):
                findings.append(
                    self._build_finding(
                        domain="compliance",
                        category="tagging",
                        severity="medium",
                        resource_id=resource_id,
                        resource_type=resource_type,
                        title=f"Recurso sin tag obligatorio: {display}",
                        description=(
                            f"El recurso {resource_id} no tiene el tag obligatorio "
                            f"'{display}'. Sin este tag no es posible asignar "
                            f"responsabilidad, centro de costo ni hacer seguimiento de gasto."
                        ),
                        recommendation=(
                            f"Agregar el tag '{display}' al recurso con un valor válido. "
                            f"Ejemplo: '{display}: nombre-equipo@empresa.com'."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={"missing_tag": display, "existing_tags": tags},
                    )
                )

        return findings
