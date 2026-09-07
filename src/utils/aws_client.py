"""
aws_client.py — Factory de clientes boto3 con configuración de retry.

Centraliza la creación de clientes AWS con:
  - Retry automático con backoff exponencial (modo adaptativo)
  - Timeouts configurados
  - Soporte para región configurable
  - Cache de clientes ya creados (evita instanciar múltiples veces)

Uso:
    from src.utils.aws_client import AWSClientFactory
    factory = AWSClientFactory(region="us-east-1")
    ec2 = factory.get_client("ec2")
    s3  = factory.get_client("s3")
"""

import os
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuración de retry adaptativo para todos los clientes
_RETRY_CONFIG = Config(
    retries={
        "max_attempts": 5,
        "mode": "adaptive",   # Adapta la velocidad según errores throttling
    },
    connect_timeout=10,
    read_timeout=30,
)


class AWSClientFactory:
    """
    Factory de clientes boto3 con retry y cache.

    Attributes:
        region:  Región AWS a usar para todos los clientes.
        session: Sesión boto3 compartida.
        _cache:  Diccionario de clientes ya instanciados (service_name → client).
    """

    def __init__(self, region: Optional[str] = None) -> None:
        self.region  = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.session = boto3.Session(region_name=self.region)
        self._cache: Dict[str, Any] = {}
        logger.debug("AWSClientFactory inicializado", extra={"region": self.region})

    def get_client(self, service_name: str, region: Optional[str] = None) -> Any:
        """
        Retorna un cliente boto3 para el servicio solicitado.

        Si el cliente ya fue creado para esa región, retorna el cached.

        Args:
            service_name: Nombre del servicio AWS (ej: "ec2", "s3", "iam").
            region:       Región opcional. Si no se especifica, usa self.region.

        Returns:
            Cliente boto3 configurado con retry adaptativo.
        """
        target_region = region or self.region
        cache_key     = f"{service_name}:{target_region}"

        if cache_key not in self._cache:
            self._cache[cache_key] = self.session.client(
                service_name,
                region_name=target_region,
                config=_RETRY_CONFIG,
            )
            logger.debug(
                "Cliente boto3 creado",
                extra={"service": service_name, "region": target_region},
            )

        return self._cache[cache_key]

    def get_resource(self, service_name: str, region: Optional[str] = None) -> Any:
        """
        Retorna un recurso boto3 de alto nivel (para S3, DynamoDB, etc.).

        Args:
            service_name: Nombre del servicio AWS.
            region:       Región opcional.

        Returns:
            Recurso boto3 configurado con retry adaptativo.
        """
        target_region = region or self.region
        return self.session.resource(
            service_name,
            region_name=target_region,
            config=_RETRY_CONFIG,
        )

    def get_account_id(self) -> str:
        """
        Retorna el ID de la cuenta AWS actual usando STS.

        Returns:
            String con el Account ID (12 dígitos).
        """
        sts = self.get_client("sts")
        identity = sts.get_caller_identity()
        return identity["Account"]

    def get_region(self) -> str:
        """Retorna la región configurada en el factory."""
        return self.region


def build_factory(region: Optional[str] = None) -> AWSClientFactory:
    """
    Helper para construir un AWSClientFactory desde variables de entorno.

    La región se resuelve en este orden:
      1. Argumento region explícito
      2. Variable de entorno AWS_DEFAULT_REGION
      3. Valor por defecto: us-east-1

    Args:
        region: Región opcional explícita.

    Returns:
        AWSClientFactory configurado.
    """
    resolved_region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return AWSClientFactory(region=resolved_region)
