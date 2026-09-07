"""
s3_checker.py — Auditoría de seguridad de Amazon S3.

Checks implementados:
  - [CRITICAL] Buckets con acceso público habilitado
  - [MEDIUM]   Buckets sin server access logging
  - [MEDIUM]   Buckets sin cifrado habilitado
"""

from __future__ import annotations

from typing import Any, Dict, List

from botocore.exceptions import ClientError

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory


class S3SecurityChecker(BaseChecker):
    """Audita configuraciones de seguridad de buckets S3."""

    REQUIRED_TAGS = ["owner", "project", "environment", "costcenter"]

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.s3 = factory.get_client("s3")

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de seguridad S3."""
        self.logger.info("Iniciando S3SecurityChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []

        try:
            buckets = self.s3.list_buckets().get("Buckets", [])
            self.logger.info("Buckets encontrados", extra={"count": len(buckets)})

            for bucket in buckets:
                name = bucket["Name"]
                tags = {}
                try:
                    tags = self._get_bucket_tags(name)
                except Exception as e:
                    self.logger.warning(
                        "Error obteniendo tags del bucket",
                        extra={"bucket": name, "error": str(e)},
                    )
                # Cada check se aísla para que un fallo en uno no impida los demás
                # (fault isolation a nivel de check individual).
                for check in (
                    self._check_public_access,
                    self._check_access_logging,
                    self._check_encryption,
                ):
                    try:
                        findings.extend(check(name, tags))
                    except Exception as e:
                        self.logger.warning(
                            "Error en check S3",
                            extra={"bucket": name, "check": check.__name__, "error": str(e)},
                        )

        except Exception as e:
            self.logger.error("Error en S3SecurityChecker", extra={"error": str(e)})

        self.logger.info(
            "S3SecurityChecker completado",
            extra={"findings": len(findings)},
        )
        return findings

    # ------------------------------------------------------------------
    # Check 1: Acceso público habilitado
    # ------------------------------------------------------------------
    def _check_public_access(self, bucket_name: str, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        try:
            resp = self.s3.get_bucket_public_access_block(Bucket=bucket_name)
            config = resp.get("PublicAccessBlockConfiguration", {})

            block_all = all([
                config.get("BlockPublicAcls", False),
                config.get("IgnorePublicAcls", False),
                config.get("BlockPublicPolicy", False),
                config.get("RestrictPublicBuckets", False),
            ])

            if not block_all:
                exposed_settings = {
                    k: v for k, v in config.items() if not v
                }
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="s3",
                        severity="critical",
                        resource_id=f"arn:aws:s3:::{bucket_name}",
                        resource_type="AWS::S3::Bucket",
                        region="global",
                        title=f"Bucket S3 con acceso público: {bucket_name}",
                        description=(
                            f"El bucket '{bucket_name}' no tiene habilitado el bloqueo "
                            f"completo de acceso público. Configuraciones no bloqueadas: "
                            f"{list(exposed_settings.keys())}. Cualquier objeto con ACL "
                            f"pública o política permisiva estará accesible desde internet."
                        ),
                        recommendation=(
                            f"Habilitar 'Block all public access' en el bucket '{bucket_name}': "
                            f"S3 → {bucket_name} → Permissions → Block public access → Edit. "
                            f"Verificar que ningún objeto requiera acceso público antes de aplicar."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={
                            "bucket_name": bucket_name,
                            "public_access_block_config": config,
                            "exposed_settings": exposed_settings,
                        },
                    )
                )

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
                # Sin configuración = acceso público NO bloqueado
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="s3",
                        severity="critical",
                        resource_id=f"arn:aws:s3:::{bucket_name}",
                        resource_type="AWS::S3::Bucket",
                        region="global",
                        title=f"Bucket S3 sin configuración de bloqueo público: {bucket_name}",
                        description=(
                            f"El bucket '{bucket_name}' no tiene configuración de "
                            f"'Block Public Access', lo que significa que el acceso "
                            f"público no está bloqueado explícitamente."
                        ),
                        recommendation=(
                            f"Habilitar 'Block all public access' en S3 → {bucket_name} "
                            f"→ Permissions → Block public access."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={"bucket_name": bucket_name, "block_config": "not_configured"},
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # Check 2: Server access logging deshabilitado
    # ------------------------------------------------------------------
    def _check_access_logging(self, bucket_name: str, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        try:
            resp = self.s3.get_bucket_logging(Bucket=bucket_name)
            logging_config = resp.get("LoggingEnabled")

            if not logging_config:
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="s3",
                        severity="medium",
                        resource_id=f"arn:aws:s3:::{bucket_name}",
                        resource_type="AWS::S3::Bucket",
                        region="global",
                        title=f"Bucket S3 sin server access logging: {bucket_name}",
                        description=(
                            f"El bucket '{bucket_name}' no tiene server access logging "
                            f"habilitado. Sin logs de acceso no es posible auditar quién "
                            f"accedió a los objetos, detectar accesos no autorizados ni "
                            f"cumplir con requisitos regulatorios de trazabilidad."
                        ),
                        recommendation=(
                            f"Habilitar server access logging en '{bucket_name}': "
                            f"S3 → {bucket_name} → Properties → Server access logging → Edit. "
                            f"Configurar un bucket destino de logs con lifecycle policy."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={"bucket_name": bucket_name, "logging_enabled": False},
                    )
                )
        except Exception as e:
            self.logger.warning(
                "Error verificando logging S3",
                extra={"bucket": bucket_name, "error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Check 3: Cifrado deshabilitado
    # ------------------------------------------------------------------
    def _check_encryption(self, bucket_name: str, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        try:
            self.s3.get_bucket_encryption(Bucket=bucket_name)
            # Si no lanza excepción, el cifrado está configurado
        except ClientError as e:
            if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="s3",
                        severity="medium",
                        resource_id=f"arn:aws:s3:::{bucket_name}",
                        resource_type="AWS::S3::Bucket",
                        region="global",
                        title=f"Bucket S3 sin cifrado en reposo: {bucket_name}",
                        description=(
                            f"El bucket '{bucket_name}' no tiene configuración de "
                            f"cifrado por defecto (SSE). Los objetos almacenados no "
                            f"están cifrados en reposo, lo que representa un riesgo "
                            f"si el almacenamiento físico es comprometido."
                        ),
                        recommendation=(
                            f"Habilitar cifrado por defecto en '{bucket_name}': "
                            f"S3 → {bucket_name} → Properties → Default encryption → Edit. "
                            f"Usar SSE-S3 (gratis) o SSE-KMS para control adicional."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={"bucket_name": bucket_name, "encryption": "not_configured"},
                    )
                )
        except Exception as e:
            self.logger.warning(
                "Error verificando cifrado S3",
                extra={"bucket": bucket_name, "error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Helper: obtener tags del bucket
    # ------------------------------------------------------------------
    def _get_bucket_tags(self, bucket_name: str) -> Dict[str, str]:
        try:
            resp = self.s3.get_bucket_tagging(Bucket=bucket_name)
            return self._extract_tags(resp.get("TagSet", []))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchTagSet":
                return {}
            raise
