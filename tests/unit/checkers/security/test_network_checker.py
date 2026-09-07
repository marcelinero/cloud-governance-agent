"""Tests unitarios de NetworkChecker (Security) con moto."""

import boto3
import pytest
from moto import mock_aws

from src.checkers.security.network_checker import NetworkChecker
from src.utils.aws_client import AWSClientFactory


@mock_aws
def test_sg_con_ssh_abierto_genera_critical(config):
    """Un Security Group con puerto 22 abierto a 0.0.0.0/0 debe generar CRITICAL."""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
    sg = ec2.create_security_group(
        GroupName="web-open-sg", Description="test", VpcId=vpc["VpcId"]
    )
    ec2.authorize_security_group_ingress(
        GroupId=sg["GroupId"],
        IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
        }],
    )

    checker = NetworkChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    ssh_findings = [f for f in findings if "SSH" in f.title]
    assert len(ssh_findings) >= 1
    assert ssh_findings[0].severity == "critical"
    assert ssh_findings[0].category == "network"


@mock_aws
def test_sg_con_puerto_restringido_no_genera_hallazgo(config):
    """Un SG con puerto 22 abierto solo a una IP específica NO debe generar hallazgo."""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
    sg = ec2.create_security_group(
        GroupName="secure-sg", Description="test", VpcId=vpc["VpcId"]
    )
    ec2.authorize_security_group_ingress(
        GroupId=sg["GroupId"],
        IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
            "IpRanges": [{"CidrIp": "203.0.113.10/32"}],
        }],
    )

    checker = NetworkChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    port_findings = [f for f in findings if "abierto al mundo" in f.title]
    assert len(port_findings) == 0


@mock_aws
def test_vpc_sin_flow_logs_genera_medium(config):
    """Una VPC sin Flow Logs debe generar un hallazgo MEDIUM."""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.create_vpc(CidrBlock="10.1.0.0/16")

    checker = NetworkChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    flow_findings = [f for f in findings if "Flow Logs" in f.title]
    assert len(flow_findings) >= 1
    assert flow_findings[0].severity == "medium"
