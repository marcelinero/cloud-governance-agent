# =============================================================================
# STACK: Frontend — Infraestructura de Muestra CGA
# =============================================================================
# ADVERTENCIA: Recursos INTENCIONALMENTE MAL CONFIGURADOS para demo del CGA.
# NO usar como referencia de buenas prácticas.
# =============================================================================

from aws_cdk import (
    Stack,
    Tags,
    CfnOutput,
    RemovalPolicy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_route53 as route53,
)
from constructs import Construct


class FrontendStack(Stack):
    """
    Crea recursos de frontend con problemas intencionales.

    HALLAZGOS ESPERADOS (Security):
    - [HIGH]   CloudFront 'cf-no-waf' sin WebACL (WAF) asociado
    - [MEDIUM] CloudFront 'cf-no-waf' permite HTTP (no fuerza HTTPS)
    - [HIGH]   CloudFront 'cf-no-waf-2' sin WAF y sin tag CostCenter

    HALLAZGOS ESPERADOS (Compliance):
    - [MEDIUM] CloudFront 'cf-no-waf-2' sin tag CostCenter
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # Bucket S3 para el origen del sitio web (bien configurado)
        # ---------------------------------------------------------------
        origin_bucket = s3.Bucket(
            self,
            "OriginBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        Tags.of(origin_bucket).add("Name",        "bucket-webapp-origin")
        Tags.of(origin_bucket).add("Owner",       "frontend@acme-corp.com")
        Tags.of(origin_bucket).add("Project",     "webapp-principal")
        Tags.of(origin_bucket).add("Environment", "production")
        Tags.of(origin_bucket).add("CostCenter",  "ENG-003")

        # ---------------------------------------------------------------
        # CloudFront #1 — SIN WAF, permite HTTP (Security: HIGH + MEDIUM)
        # Simula la distribución principal de la webapp sin protección
        # ---------------------------------------------------------------
        cf_no_waf = cloudfront.Distribution(
            self,
            "CfNoWaf",
            comment="webapp-principal - SIN WAF - demo CGA",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    origin_bucket
                ),
                # Permite HTTP — no fuerza HTTPS — hallazgo MEDIUM
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.ALLOW_ALL,
                # Sin cache optimizado
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            ),
            # Sin web_acl_id — sin WAF — hallazgo HIGH
            # web_acl_id no especificado intencionalmente
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
            # Sin logging habilitado
            enable_logging=False,
        )

        Tags.of(cf_no_waf).add("Name",        "cf-webapp-principal")
        Tags.of(cf_no_waf).add("Owner",       "frontend@acme-corp.com")
        Tags.of(cf_no_waf).add("Project",     "webapp-principal")
        Tags.of(cf_no_waf).add("Environment", "production")
        Tags.of(cf_no_waf).add("CostCenter",  "ENG-003")
        Tags.of(cf_no_waf).add("Note",        "Sin WAF - HTTP permitido - hallazgo CGA")

        # ---------------------------------------------------------------
        # Bucket S3 para segunda distribución
        # ---------------------------------------------------------------
        origin_bucket_2 = s3.Bucket(
            self,
            "OriginBucket2",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        Tags.of(origin_bucket_2).add("Name",        "bucket-adminpanel-origin")
        Tags.of(origin_bucket_2).add("Owner",       "frontend@acme-corp.com")
        Tags.of(origin_bucket_2).add("Project",     "admin-panel")
        Tags.of(origin_bucket_2).add("Environment", "production")
        Tags.of(origin_bucket_2).add("CostCenter",  "ENG-003")

        # ---------------------------------------------------------------
        # CloudFront #2 — Panel admin SIN WAF, sin CostCenter (Security: HIGH)
        # Simula un panel de administración expuesto sin protección WAF
        # ---------------------------------------------------------------
        cf_admin_no_waf = cloudfront.Distribution(
            self,
            "CfAdminNoWaf",
            comment="admin-panel - SIN WAF - demo CGA",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    origin_bucket_2
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            # Sin web_acl_id — sin WAF — hallazgo HIGH
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            enable_logging=False,
        )

        Tags.of(cf_admin_no_waf).add("Name",        "cf-admin-panel")
        Tags.of(cf_admin_no_waf).add("Owner",       "frontend@acme-corp.com")
        Tags.of(cf_admin_no_waf).add("Project",     "admin-panel")
        Tags.of(cf_admin_no_waf).add("Environment", "production")
        # CostCenter ausente intencionalmente — hallazgo compliance
        Tags.of(cf_admin_no_waf).add("Note",        "Panel admin sin WAF - hallazgo CGA")

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "CfNoWafDomain",
                  value=cf_no_waf.distribution_domain_name,
                  export_name="SampleCfNoWafDomain")
        CfnOutput(self, "CfAdminNoWafDomain",
                  value=cf_admin_no_waf.distribution_domain_name,
                  export_name="SampleCfAdminDomain")
        CfnOutput(self, "OriginBucketName",
                  value=origin_bucket.bucket_name,
                  export_name="SampleOriginBucketName")
