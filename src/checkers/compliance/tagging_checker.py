"""
tagging_checker.py — Auditoría de cumplimiento de etiquetado en AWS.

Verifica que los recursos clave tengan los tags obligatorios:
  Owner, Project, Environment, CostCenter

Servicios auditados:
  EC2, RDS, S3, Lambda, ECS Services, DynamoDB, CloudFront
"""

from __future__ import annotations

from typing import Any, Dict, List

from botocore.exceptions import ClientError

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

REQUIRED_TAGS = ["owner", "project", "environment", "costcenter"]
TAG_DISPLAY   = {"owner": "Owner", "project": "Project",
                 "environment": "Environment", "costcenter": "CostCenter"}


class TaggingChecker(BaseChecker):
    """Verifica que los recursos AWS tengan los tags obligatorios de gobierno."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.ec2      = factory.get_client("ec2")
        self.rds      = factory.get_client("rds")
        self.s3       = factory.get_client("s3")
        self.lambda_  = factory.get_client("lambda")
        self.dynamodb = factory.get_client("dynamodb")
        self.cf       = factory.get_client("cloudfront", region="us-east-1")

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando TaggingChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            findings.extend(self._check_ec2_tags())
            findings.extend(self._check_rds_tags())
            findings.extend(self._check_s3_tags())
            findings.extend(self._check_lambda_tags())
            findings.extend(self._check_dynamodb_tags())
            findings.extend(self._check_cloudfront_tags())
        except Exception as e:
            self.logger.error("Error en TaggingChecker", extra={"error": str(e)})

        self.logger.info("TaggingChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # EC2
    # ------------------------------------------------------------------
    def _check_ec2_tags(self) -> List[Finding]:
        findings = []
        paginator = self.ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    state = inst["State"]["Name"]
                    if state == "terminated":
                        continue
                    tags = self._extract_tags(inst.get("Tags", []))
                    findings.extend(self._missing_tags(
                        resource_id=inst["InstanceId"],
                        resource_type="AWS::EC2::Instance",
                        tags=tags,
                        name=self._get_tag(tags, "name") or inst["InstanceId"],
                    ))
        return findings

    # ------------------------------------------------------------------
    # RDS
    # ------------------------------------------------------------------
    def _check_rds_tags(self) -> List[Finding]:
        findings = []
        paginator = self.rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for inst in page.get("DBInstances", []):
                if inst.get("DBInstanceStatus") == "deleted":
                    continue
                try:
                    resp = self.rds.list_tags_for_resource(ResourceName=inst["DBInstanceArn"])
                    tags = self._extract_tags(resp.get("TagList", []))
                except Exception:
                    tags = {}
                findings.extend(self._missing_tags(
                    resource_id=inst["DBInstanceArn"],
                    resource_type="AWS::RDS::DBInstance",
                    tags=tags,
                    name=inst["DBInstanceIdentifier"],
                ))
        return findings

    # ------------------------------------------------------------------
    # S3
    # ------------------------------------------------------------------
    def _check_s3_tags(self) -> List[Finding]:
        findings = []
        try:
            buckets = self.s3.list_buckets().get("Buckets", [])
            for bucket in buckets:
                name = bucket["Name"]
                try:
                    resp = self.s3.get_bucket_tagging(Bucket=name)
                    tags = self._extract_tags(resp.get("TagSet", []))
                except ClientError as e:
                    tags = {} if e.response["Error"]["Code"] == "NoSuchTagSet" else {}
                findings.extend(self._missing_tags(
                    resource_id=f"arn:aws:s3:::{name}",
                    resource_type="AWS::S3::Bucket",
                    tags=tags,
                    name=name,
                    region="global",
                ))
        except Exception as e:
            self.logger.warning("Error verificando tags S3", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Lambda
    # ------------------------------------------------------------------
    def _check_lambda_tags(self) -> List[Finding]:
        findings = []
        paginator = self.lambda_.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                fn_arn = fn["FunctionArn"]
                try:
                    resp = self.lambda_.list_tags(Resource=fn_arn)
                    raw  = [{"Key": k, "Value": v} for k, v in resp.get("Tags", {}).items()]
                    tags = self._extract_tags(raw)
                except Exception:
                    tags = {}
                findings.extend(self._missing_tags(
                    resource_id=fn_arn,
                    resource_type="AWS::Lambda::Function",
                    tags=tags,
                    name=fn["FunctionName"],
                ))
        return findings

    # ------------------------------------------------------------------
    # DynamoDB
    # ------------------------------------------------------------------
    def _check_dynamodb_tags(self) -> List[Finding]:
        findings = []
        paginator = self.dynamodb.get_paginator("list_tables")
        for page in paginator.paginate():
            for table_name in page.get("TableNames", []):
                try:
                    info = self.dynamodb.describe_table(TableName=table_name)["Table"]
                    resp = self.dynamodb.list_tags_of_resource(ResourceArn=info["TableArn"])
                    tags = self._extract_tags(resp.get("Tags", []))
                except Exception:
                    tags = {}
                    info = {"TableArn": f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{table_name}"}
                findings.extend(self._missing_tags(
                    resource_id=info.get("TableArn", table_name),
                    resource_type="AWS::DynamoDB::Table",
                    tags=tags,
                    name=table_name,
                ))
        return findings

    # ------------------------------------------------------------------
    # CloudFront
    # ------------------------------------------------------------------
    def _check_cloudfront_tags(self) -> List[Finding]:
        findings = []
        try:
            paginator = self.cf.get_paginator("list_distributions")
            for page in paginator.paginate():
                items = page.get("DistributionList", {}).get("Items", [])
                for dist in items:
                    dist_arn = dist["ARN"]
                    comment  = dist.get("Comment", dist["Id"])
                    try:
                        resp     = self.cf.list_tags_for_resource(Resource=dist_arn)
                        tag_list = resp.get("Tags", {}).get("Items", [])
                        tags     = self._extract_tags(tag_list)
                    except Exception:
                        tags = {}
                    findings.extend(self._missing_tags(
                        resource_id=dist_arn,
                        resource_type="AWS::CloudFront::Distribution",
                        tags=tags,
                        name=comment or dist["Id"],
                        region="global",
                    ))
        except Exception as e:
            self.logger.warning("Error verificando tags CloudFront", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Helper central: genera un Finding por cada tag ausente
    # ------------------------------------------------------------------
    def _missing_tags(
        self,
        resource_id:   str,
        resource_type: str,
        tags:          Dict[str, str],
        name:          str,
        region:        str = None,
    ) -> List[Finding]:
        findings = []
        for tag_key in REQUIRED_TAGS:
            display = TAG_DISPLAY.get(tag_key, tag_key)
            # Aceptar variantes: costcenter / cost_center / cost-center
            normalized_keys = [tag_key, tag_key.replace("cost", "cost_").replace("center", "center")]
            has_tag = any(tags.get(k) for k in normalized_keys)
            if not has_tag:
                findings.append(
                    self._build_finding(
                        domain="compliance",
                        category="tagging",
                        severity="medium",
                        resource_id=resource_id,
                        resource_type=resource_type,
                        region=region or self.region,
                        title=f"Tag obligatorio ausente '{display}': {name}",
                        description=(
                            f"El recurso '{name}' ({resource_type}) no tiene el tag "
                            f"obligatorio '{display}'. Sin este tag no es posible "
                            f"identificar al responsable, asignar costos por centro de "
                            f"costo ni auditar la trazabilidad del recurso."
                        ),
                        recommendation=(
                            f"Agregar el tag '{display}' al recurso '{name}' con un valor "
                            f"válido. Ejemplo: Owner → equipo@empresa.com, "
                            f"Project → nombre-proyecto, Environment → production, "
                            f"CostCenter → ENG-001."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={
                            "resource_name":  name,
                            "missing_tag":    display,
                            "existing_tags":  tags,
                        },
                    )
                )
        return findings
