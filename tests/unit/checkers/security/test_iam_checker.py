"""Tests unitarios de IAMChecker con moto."""

import boto3
import pytest
from moto import mock_aws

from src.checkers.security.iam_checker import IAMChecker
from src.utils.aws_client import AWSClientFactory


@mock_aws
def test_usuario_con_admin_access_directo_genera_critical(config):
    """Un usuario con AdministratorAccess adjunto directamente debe generar CRITICAL.

    Nota: moto 5.x no precarga las AWS managed policies, así que creamos una
    customer managed policy con el nombre 'AdministratorAccess' y contenido de
    acceso total para reproducir el escenario.
    """
    iam = boto3.client("iam", region_name="us-east-1")
    iam.create_user(UserName="dev-admin")
    policy = iam.create_policy(
        PolicyName="AdministratorAccess",
        PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}',
    )
    iam.attach_user_policy(
        UserName="dev-admin",
        PolicyArn=policy["Policy"]["Arn"],
    )

    checker = IAMChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    admin_findings = [f for f in findings if "AdministratorAccess" in f.title]
    assert len(admin_findings) >= 1
    assert admin_findings[0].severity == "critical"
    assert admin_findings[0].category == "iam"


@mock_aws
def test_usuario_sin_politicas_no_genera_admin_hallazgo(config):
    """Un usuario sin políticas administrativas no debe generar hallazgo de AdminAccess."""
    iam = boto3.client("iam", region_name="us-east-1")
    iam.create_user(UserName="usuario-limitado")

    checker = IAMChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    admin_findings = [f for f in findings if "AdministratorAccess" in f.title]
    assert len(admin_findings) == 0


@mock_aws
def test_politica_inline_wildcard_genera_high(config):
    """Un usuario con política inline *:* debe generar hallazgo HIGH."""
    iam = boto3.client("iam", region_name="us-east-1")
    iam.create_user(UserName="usuario-emergencia")
    iam.put_user_policy(
        UserName="usuario-emergencia",
        PolicyName="full-access",
        PolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}',
    )

    checker = IAMChecker(AWSClientFactory(region="us-east-1"), config)
    findings = checker.run()

    wildcard = [f for f in findings if "*:*" in f.title or "inline" in f.title.lower()]
    assert len(wildcard) >= 1
    assert wildcard[0].severity == "high"
