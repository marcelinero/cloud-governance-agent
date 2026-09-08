"""
cloudfront_checker.py — Auditoría de seguridad de Amazon CloudFront.

Checks implementados:
  - [HIGH]   Distribuciones sin WebACL (WAF) asociado
  - [MEDIUM] Distribuciones que permiten HTTP (no fuerzan HTTPS)

Nota: nombres de AWS Managed Rules (AWSManagedRulesCommonRuleSet,
AWSManagedRulesBotControlRuleSet) validados vigentes contra la documentación
oficial de AWS WAF.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory


class CloudFrontChecker(BaseChecker):
    """Audita configuraciones de seguridad de distribuciones CloudFront."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        # CloudFront es global — siempre us-east-1
        self.cf = factory.get_client("cloudfront", region="us-east-1")

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de seguridad CloudFront."""
        self.logger.info("Iniciando CloudFrontChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []

        try:
            distributions = self._list_all_distributions()
            self.logger.info(
                "Distribuciones CloudFront encontradas",
                extra={"count": len(distributions)},
            )

            for dist in distributions:
                try:
                    dist_id  = dist["Id"]
                    dist_arn = dist["ARN"]
                    tags     = self._get_cf_tags(dist_arn)
                    findings.extend(self._check_waf(dist, tags))
                    findings.extend(self._check_https(dist, tags))
                except Exception as e:
                    self.logger.warning(
                        "Error auditando distribución CF",
                        extra={"distribution": dist.get("Id"), "error": str(e)},
                    )

        except Exception as e:
            self.logger.error("Error en CloudFrontChecker", extra={"error": str(e)})

        self.logger.info(
            "CloudFrontChecker completado",
            extra={"findings": len(findings)},
        )
        return findings

    # ------------------------------------------------------------------
    # Check 1: Sin WAF asociado
    # ------------------------------------------------------------------
    def _check_waf(self, dist: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        dist_id     = dist["Id"]
        dist_arn    = dist["ARN"]
        domain_name = dist.get("DomainName", "")
        comment     = dist.get("Comment", dist_id)
        config      = dist.get("DistributionConfig", {})
        web_acl_id  = config.get("WebACLId", "")

        if not web_acl_id:
            findings.append(
                self._build_finding(
                    domain="security",
                    category="cloudfront",
                    severity="high",
                    resource_id=dist_arn,
                    resource_type="AWS::CloudFront::Distribution",
                    region="global",
                    title=f"CloudFront sin WAF: {comment or dist_id}",
                    description=(
                        f"La distribución CloudFront '{comment}' ({dist_id}, "
                        f"{domain_name}) no tiene un WebACL de AWS WAF asociado. "
                        f"Sin WAF la distribución está expuesta a ataques comunes: "
                        f"SQL injection, XSS, bots, DDoS Layer 7 y scrapers."
                    ),
                    recommendation=(
                        f"Asociar un WebACL de AWS WAF a la distribución '{dist_id}': "
                        f"WAF → Web ACLs → Create web ACL (región: CloudFront/Global). "
                        f"Incluir reglas AWS Managed Rules para protección básica: "
                        f"AWSManagedRulesCommonRuleSet y AWSManagedRulesBotControlRuleSet."
                    ),
                    owner=self._get_tag(tags, "owner"),
                    project=self._get_tag(tags, "project"),
                    environment=self._get_tag(tags, "environment"),
                    cost_center=self._get_tag(tags, "costcenter"),
                    evidence={
                        "distribution_id":  dist_id,
                        "domain_name":      domain_name,
                        "comment":          comment,
                        "web_acl_id":       "not_configured",
                        "status":           dist.get("Status"),
                        "price_class":      config.get("PriceClass"),
                    },
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Check 2: HTTP permitido (no forzando HTTPS)
    # ------------------------------------------------------------------
    def _check_https(self, dist: Dict, tags: Dict[str, str]) -> List[Finding]:
        findings = []
        dist_id     = dist["Id"]
        dist_arn    = dist["ARN"]
        comment     = dist.get("Comment", dist_id)
        config      = dist.get("DistributionConfig", {})

        cache_behaviors = [config.get("DefaultCacheBehavior", {})]
        cache_behaviors += config.get("CacheBehaviors", {}).get("Items", [])

        for behavior in cache_behaviors:
            protocol_policy = behavior.get("ViewerProtocolPolicy", "")
            if protocol_policy == "allow-all":
                path = behavior.get("PathPattern", "default (*)")
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="cloudfront",
                        severity="medium",
                        resource_id=dist_arn,
                        resource_type="AWS::CloudFront::Distribution",
                        region="global",
                        title=f"CloudFront permite HTTP sin cifrar: {comment or dist_id}",
                        description=(
                            f"La distribución CloudFront '{comment}' ({dist_id}) "
                            f"tiene ViewerProtocolPolicy='allow-all' en el behavior "
                            f"'{path}', permitiendo que los usuarios accedan via HTTP "
                            f"sin cifrado. Los datos en tránsito pueden ser interceptados."
                        ),
                        recommendation=(
                            f"Cambiar ViewerProtocolPolicy a 'redirect-to-https' o "
                            f"'https-only' en la distribución '{dist_id}'. "
                            f"CloudFront → {dist_id} → Behaviors → Edit → "
                            f"Viewer Protocol Policy → Redirect HTTP to HTTPS."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={
                            "distribution_id":       dist_id,
                            "comment":               comment,
                            "behavior_path":         path,
                            "viewer_protocol_policy": protocol_policy,
                        },
                    )
                )
                break  # Un hallazgo por distribución es suficiente

        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _list_all_distributions(self) -> List[Dict]:
        """Lista todas las distribuciones CloudFront de la cuenta."""
        distributions = []
        paginator = self.cf.get_paginator("list_distributions")
        for page in paginator.paginate():
            items = page.get("DistributionList", {}).get("Items", [])
            distributions.extend(items)
        return distributions

    def _get_cf_tags(self, resource_arn: str) -> Dict[str, str]:
        """Obtiene los tags de una distribución CloudFront."""
        try:
            resp = self.cf.list_tags_for_resource(Resource=resource_arn)
            tag_list = resp.get("Tags", {}).get("Items", [])
            return self._extract_tags(tag_list)
        except Exception:
            return {}
