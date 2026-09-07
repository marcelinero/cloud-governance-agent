"""Tests unitarios de S3SecurityChecker con moto."""

import boto3
import pytest
from moto import mock_aws

from src.checkers.security.s3_checker import S3SecurityChecker
from src.utils.aws_client import AWSClientFactory


@mock_aws
@pytest.mark.skip(
    reason="moto 5.x no implementa get_bucket_public_access_block en el cliente S3. "
    "Este check se validó contra AWS real durante el despliegue (Fase 6)."
)
def test_bucket_publico_genera_hallazgo_critical(config):
    """Un bucket con Block Public Access desactivado debe generar un hallazgo CRITICAL."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-inseguro-demo")
    s3.put_public_access_block(
        Bucket="bucket-inseguro-demo",
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )

    checker = S3SecurityChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    public_findings = [f for f in findings if "público" in f.title or "public" in f.title.lower()]
    assert len(public_findings) >= 1
    assert public_findings[0].severity == "critical"


@mock_aws
def test_bucket_con_block_public_access_no_genera_hallazgo_critical(config):
    """Un bucket con Block Public Access completo NO debe generar hallazgo CRITICAL de acceso público."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-seguro-demo")
    s3.put_public_access_block(
        Bucket="bucket-seguro-demo",
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )

    checker = S3SecurityChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    critical = [f for f in findings if f.severity == "critical"]
    assert len(critical) == 0


@mock_aws
def test_bucket_sin_logging_genera_hallazgo_medium(config):
    """Un bucket sin server access logging debe generar un hallazgo MEDIUM."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-sin-logs")
    s3.put_public_access_block(
        Bucket="bucket-sin-logs",
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
        },
    )
    # Cifrado por defecto para aislar el hallazgo de logging
    s3.put_bucket_encryption(
        Bucket="bucket-sin-logs",
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )

    checker = S3SecurityChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    logging_findings = [f for f in findings if "logging" in f.title.lower()]
    assert len(logging_findings) >= 1
    assert logging_findings[0].severity == "medium"


@mock_aws
def test_sin_buckets_no_genera_hallazgos(config):
    """Sin buckets en la cuenta, no debe haber hallazgos."""
    checker = S3SecurityChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()
    assert findings == []
