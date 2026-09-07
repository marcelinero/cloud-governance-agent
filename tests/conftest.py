"""
conftest.py — Fixtures compartidas para los tests del Cloud Governance Agent.

Provee:
  - Credenciales AWS mock (evita usar credenciales reales)
  - Configuración base para los checkers
  - Factory de clientes boto3 apuntando a moto
"""

import os

import boto3
import pytest
from moto import mock_aws

from src.utils.aws_client import AWSClientFactory

TEST_ACCOUNT_ID = "123456789012"
TEST_REGION = "us-east-1"


@pytest.fixture(autouse=True)
def aws_credentials():
    """Credenciales AWS mock para todos los tests (evita llamadas reales)."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = TEST_REGION
    yield


@pytest.fixture
def config():
    """Configuración base para instanciar checkers en tests."""
    return {
        "account_id":               TEST_ACCOUNT_ID,
        "region":                   TEST_REGION,
        "account_name":             "Test Account",
        "cpu_threshold_percent":    10,
        "stopped_days_threshold":   7,
        "key_age_days_threshold":   90,
        "lambda_inactive_days":     30,
        "snapshot_age_days":        30,
        "ami_age_days":             90,
        "dynamodb_ops_threshold":   10,
        "inactive_days_threshold":  90,
    }


@pytest.fixture
def factory():
    """
    AWSClientFactory usable dentro de un contexto @mock_aws.

    El test debe estar decorado con @mock_aws para que los clientes
    apunten a los mocks de moto.
    """
    return AWSClientFactory(region=TEST_REGION)
