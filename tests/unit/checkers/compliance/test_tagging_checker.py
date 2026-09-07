"""Tests unitarios del TaggingChecker con moto."""

import boto3
import pytest
from moto import mock_aws

from src.checkers.compliance.tagging_checker import TaggingChecker
from src.utils.aws_client import AWSClientFactory


@mock_aws
def test_bucket_sin_tags_genera_hallazgos_por_cada_tag(config):
    """Un bucket S3 sin tags obligatorios debe generar un hallazgo por cada tag ausente."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-sin-tags")

    checker = TaggingChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    bucket_findings = [
        f for f in findings if "bucket-sin-tags" in f.resource_id
    ]
    # 4 tags obligatorios: Owner, Project, Environment, CostCenter
    assert len(bucket_findings) == 4
    assert all(f.domain == "compliance" for f in bucket_findings)
    assert all(f.category == "tagging" for f in bucket_findings)
    assert all(f.severity == "medium" for f in bucket_findings)


@mock_aws
def test_bucket_con_todos_los_tags_no_genera_hallazgos(config):
    """Un bucket con los 4 tags obligatorios no debe generar hallazgos de tagging."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-con-tags")
    s3.put_bucket_tagging(
        Bucket="bucket-con-tags",
        Tagging={"TagSet": [
            {"Key": "Owner", "Value": "team@empresa.com"},
            {"Key": "Project", "Value": "proyecto-x"},
            {"Key": "Environment", "Value": "production"},
            {"Key": "CostCenter", "Value": "ENG-001"},
        ]},
    )

    checker = TaggingChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    bucket_findings = [f for f in findings if "bucket-con-tags" in f.resource_id]
    assert len(bucket_findings) == 0
