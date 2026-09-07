"""Tests unitarios de StorageChecker (FinOps) con moto."""

import boto3
import pytest
from moto import mock_aws

from src.checkers.finops.storage_checker import StorageChecker
from src.utils.aws_client import AWSClientFactory


@mock_aws
def test_bucket_sin_lifecycle_genera_hallazgo(config):
    """Un bucket sin lifecycle policy debe generar un hallazgo FinOps MEDIUM."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-sin-lifecycle")

    checker = StorageChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    lifecycle = [f for f in findings if "lifecycle" in f.title.lower()]
    assert len(lifecycle) >= 1
    assert lifecycle[0].domain == "finops"
    assert lifecycle[0].severity == "medium"


@mock_aws
def test_volumen_ebs_disponible_genera_hallazgo(config):
    """Un volumen EBS en estado 'available' debe generar hallazgo con costo estimado.

    El volumen recién creado en moto tiene 0 días de antigüedad, así que usamos
    umbral 0 para validar la lógica de detección y estimación de costo.
    """
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.create_volume(AvailabilityZone="us-east-1a", Size=50, VolumeType="gp3")

    config_umbral_0 = {**config, "stopped_days_threshold": 0}
    checker = StorageChecker(AWSClientFactory(region="us-east-1"), config_umbral_0)
    findings = checker.run()

    ebs = [f for f in findings if f.resource_type == "AWS::EC2::Volume"]
    assert len(ebs) >= 1
    assert ebs[0].domain == "finops"
    assert ebs[0].estimated_monthly_cost > 0
    assert ebs[0].potential_saving > 0


@mock_aws
def test_bucket_con_lifecycle_no_genera_hallazgo_lifecycle(config):
    """Un bucket con lifecycle configurada no debe generar el hallazgo de lifecycle."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bucket-con-lifecycle")
    s3.put_bucket_lifecycle_configuration(
        Bucket="bucket-con-lifecycle",
        LifecycleConfiguration={
            "Rules": [{
                "ID": "expire", "Status": "Enabled",
                "Expiration": {"Days": 90}, "Filter": {"Prefix": ""},
            }]
        },
    )

    checker = StorageChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    lifecycle = [
        f for f in findings
        if "lifecycle" in f.title.lower() and "bucket-con-lifecycle" in f.resource_id
    ]
    assert len(lifecycle) == 0
