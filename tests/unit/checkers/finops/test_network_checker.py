"""Tests unitarios de NetworkFinOpsChecker con moto."""

import boto3
import pytest
from moto import mock_aws

from src.checkers.finops.network_checker import NetworkFinOpsChecker
from src.utils.aws_client import AWSClientFactory


@mock_aws
def test_eip_no_asociada_genera_hallazgo_low(config):
    """Una Elastic IP no asociada debe generar un hallazgo FinOps LOW con costo."""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.allocate_address(Domain="vpc")

    checker = NetworkFinOpsChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    eip = [f for f in findings if f.resource_type == "AWS::EC2::EIP"]
    assert len(eip) >= 1
    assert eip[0].domain == "finops"
    assert eip[0].severity == "low"
    assert eip[0].potential_saving > 0


@mock_aws
def test_eip_asociada_no_genera_hallazgo(config):
    """Una Elastic IP asociada a una instancia NO debe generar hallazgo."""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    # Lanzar una instancia y asociar la EIP
    reservation = ec2.run_instances(
        ImageId="ami-12345678", MinCount=1, MaxCount=1, InstanceType="t3.micro"
    )
    instance_id = reservation["Instances"][0]["InstanceId"]
    alloc = ec2.allocate_address(Domain="vpc")
    ec2.associate_address(InstanceId=instance_id, AllocationId=alloc["AllocationId"])

    checker = NetworkFinOpsChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    eip = [f for f in findings if f.resource_type == "AWS::EC2::EIP"]
    assert len(eip) == 0


@mock_aws
def test_sin_recursos_red_no_genera_hallazgos(config):
    """Sin EIPs, NAT ni LBs, no debe haber hallazgos de red FinOps."""
    checker = NetworkFinOpsChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()
    eip = [f for f in findings if f.resource_type == "AWS::EC2::EIP"]
    assert eip == []
