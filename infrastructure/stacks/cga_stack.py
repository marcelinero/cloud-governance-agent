"""
CGAStack — Stack principal del Cloud Governance Agent.

Despliega todos los recursos AWS necesarios para el agente:
  - Lambda (orquestador)
  - S3 (bucket de reportes)
  - IAM Role (mínimo privilegio)
  - EventBridge Rule (schedule semanal)
  - CloudWatch Log Group + Alarma
  - SNS Topic (alertas de fallo)
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    CfnOutput,
)
from constructs import Construct


class CGAStack(Stack):
    """Stack principal del Cloud Governance Agent."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Leer configuración desde cdk.json context
        account_name        = self.node.try_get_context("account_name")        or "AWS Account"
        audit_email         = self.node.try_get_context("audit_email")         or ""
        finops_email        = self.node.try_get_context("finops_email")        or ""
        security_email      = self.node.try_get_context("security_email")      or ""
        ses_sender_email    = self.node.try_get_context("ses_sender_email")    or ""
        cpu_threshold       = self.node.try_get_context("cpu_threshold_percent")    or "10"
        stopped_days        = self.node.try_get_context("stopped_days_threshold")   or "7"
        key_age_days        = self.node.try_get_context("key_age_days_threshold")   or "90"

        # ---------------------------------------------------------------
        # S3 — Bucket de reportes
        # ---------------------------------------------------------------
        reports_bucket = s3.Bucket(
            self,
            "ReportsBucket",
            bucket_name=f"cga-reports-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-reports-365d",
                    expiration=Duration.days(365),
                    enabled=True,
                )
            ],
        )

        # ---------------------------------------------------------------
        # IAM Role — Mínimo privilegio para la Lambda
        # ---------------------------------------------------------------
        lambda_role = iam.Role(
            self,
            "CgaLambdaRole",
            role_name="cga-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Rol IAM para el Cloud Governance Agent - minimo privilegio",
        )

        # Permisos de logging (managed policy básica de Lambda)
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # Permisos de auditoría — solo lectura sobre servicios auditados
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaEC2ReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:DescribeInstances",
                    "ec2:DescribeVolumes",
                    "ec2:DescribeSnapshots",
                    "ec2:DescribeImages",
                    "ec2:DescribeAddresses",
                    "ec2:DescribeNatGateways",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeFlowLogs",
                    "ec2:DescribeRegions",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaRDSReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "rds:DescribeDBInstances",
                    "rds:DescribeDBClusters",
                    "rds:ListTagsForResource",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaS3ReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ListAllMyBuckets",
                    "s3:GetBucketAcl",
                    "s3:GetBucketPolicy",
                    "s3:GetBucketLogging",
                    "s3:GetBucketLifecycleConfiguration",
                    "s3:GetBucketPublicAccessBlock",
                    "s3:GetBucketVersioning",
                    "s3:GetBucketTagging",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaS3PutReports",
                effect=iam.Effect.ALLOW,
                actions=["s3:PutObject"],
                resources=[f"{reports_bucket.bucket_arn}/*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaIAMReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:ListUsers",
                    "iam:ListAccessKeys",
                    "iam:GetLoginProfile",
                    "iam:ListAttachedUserPolicies",
                    "iam:ListUserPolicies",
                    "iam:GetUserPolicy",
                    "iam:ListMFADevices",
                    "iam:GenerateCredentialReport",
                    "iam:GetCredentialReport",
                    "iam:ListPolicies",
                    "iam:GetPolicy",
                    "iam:GetPolicyVersion",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaLambdaReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:ListFunctions",
                    "lambda:GetFunction",
                    "lambda:ListTags",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaCloudfrontReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudfront:ListDistributions",
                    "cloudfront:GetDistribution",
                    "cloudfront:ListTagsForResource",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaCloudTrailReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudtrail:GetTrailStatus",
                    "cloudtrail:DescribeTrails",
                    "cloudtrail:ListTrails",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaCloudWatchReadWrite",
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:GetMetricData",
                    "cloudwatch:PutMetricData",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaCostExplorer",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ce:GetCostAndUsage",
                    "ce:GetCostForecast",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaSESSend",
                effect=iam.Effect.ALLOW,
                actions=["ses:SendRawEmail", "ses:SendEmail"],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaDynamoDBReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:ListTables",
                    "dynamodb:DescribeTable",
                    "dynamodb:ListTagsOfResource",
                ],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="CgaELBReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "elasticloadbalancing:DescribeLoadBalancers",
                    "elasticloadbalancing:DescribeTargetGroups",
                    "elasticloadbalancing:DescribeTags",
                ],
                resources=["*"],
            )
        )

        # ---------------------------------------------------------------
        # CloudWatch Log Group
        # ---------------------------------------------------------------
        log_group = logs.LogGroup(
            self,
            "CgaLogGroup",
            log_group_name="/aws/lambda/cloud-governance-agent",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------------------------------------------------------------
        # Lambda — CGA Orchestrator
        # ---------------------------------------------------------------
        cga_lambda = _lambda.Function(
            self,
            "CgaOrchestrator",
            function_name="cloud-governance-agent",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="src.handler.lambda_handler",
            # Empaqueta desde la raiz del proyecto incluyendo solo el paquete src/,
            # de modo que "src" sea importable en Lambda y los imports absolutos
            # (from src.xxx) funcionen igual que en ejecucion local y tests.
            code=_lambda.Code.from_asset(
                "..",
                exclude=[
                    "*", "!src", "!src/**",
                    "**/__pycache__", "**/*.pyc",
                ],
            ),
            role=lambda_role,
            timeout=Duration.seconds(900),
            memory_size=512,
            log_group=log_group,
            environment={
                "REPORTS_BUCKET":          reports_bucket.bucket_name,
                "AUDIT_EMAIL":             audit_email,
                "FINOPS_EMAIL":            finops_email,
                "SECURITY_EMAIL":          security_email,
                "SES_SENDER_EMAIL":        ses_sender_email,
                "AWS_ACCOUNT_NAME":        account_name,
                "CPU_THRESHOLD_PERCENT":   cpu_threshold,
                "STOPPED_DAYS_THRESHOLD":  stopped_days,
                "KEY_AGE_DAYS_THRESHOLD":  key_age_days,
                "LOG_LEVEL":               "INFO",
            },
            description="Cloud Governance Agent - Auditoria continua de seguridad y costos",
        )

        # ---------------------------------------------------------------
        # EventBridge Rule — Lunes 08:00 AM UTC
        # ---------------------------------------------------------------
        schedule_rule = events.Rule(
            self,
            "CgaScheduleRule",
            rule_name="cga-weekly-schedule",
            description="Ejecuta el CGA todos los lunes a las 08:00 AM UTC",
            schedule=events.Schedule.cron(
                minute="0",
                hour="8",
                week_day="MON",
                month="*",
                year="*",
            ),
        )

        schedule_rule.add_target(
            targets.LambdaFunction(
                cga_lambda,
                event=events.RuleTargetInput.from_object(
                    {"execution_type": "scheduled", "source": "eventbridge"}
                ),
            )
        )

        # ---------------------------------------------------------------
        # SNS Topic — Alertas de fallo de la Lambda
        # ---------------------------------------------------------------
        alarm_topic = sns.Topic(
            self,
            "CgaAlarmTopic",
            topic_name="cga-lambda-alarms",
            display_name="CGA Lambda Alarms",
        )

        # Suscripcion por email a las alarmas. Deshabilitada en modo demo porque
        # los emails placeholder (@acme-corp.com) no son confirmables y dejan
        # suscripciones "pending" que complican los rollbacks. Para uso real,
        # descomentar y usar un email valido (confirmar el correo de suscripcion).
        # if audit_email and not audit_email.endswith("@acme-corp.com"):
        #     alarm_topic.add_subscription(
        #         subscriptions.EmailSubscription(audit_email)
        #     )

        # ---------------------------------------------------------------
        # CloudWatch Alarm — Error en la Lambda
        # ---------------------------------------------------------------
        error_alarm = cloudwatch.Alarm(
            self,
            "CgaErrorAlarm",
            alarm_name="CGA-Lambda-Errors",
            alarm_description="El Cloud Governance Agent falló en su ejecución",
            metric=cga_lambda.metric_errors(
                period=Duration.minutes(5),
                statistic="Sum",
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        error_alarm.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)
        )

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "LambdaFunctionName",
                  value=cga_lambda.function_name,
                  description="Nombre de la función Lambda del CGA")

        CfnOutput(self, "ReportsBucketName",
                  value=reports_bucket.bucket_name,
                  description="Bucket S3 donde se almacenan los reportes")

        CfnOutput(self, "LogGroupName",
                  value=log_group.log_group_name,
                  description="CloudWatch Log Group del CGA")

        CfnOutput(self, "InvokeCommand",
                  value=f"aws lambda invoke --function-name {cga_lambda.function_name} --payload '{{\"execution_type\":\"on-demand\"}}' --cli-binary-format raw-in-base64-out response.json",
                  description="Comando para invocar el CGA bajo demanda")
