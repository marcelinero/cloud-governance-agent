# =============================================================================
# STACK: IAM — Infraestructura de Muestra CGA
# =============================================================================
# ADVERTENCIA: Recursos INTENCIONALMENTE MAL CONFIGURADOS para demo del CGA.
# NO usar como referencia de buenas prácticas.
# =============================================================================
# NOTA DE SEGURIDAD: Los usuarios IAM creados aquí NO tienen contraseña
# de consola habilitada por defecto. Las access keys se crean para simular
# el hallazgo de "key sin rotación", pero deben eliminarse tras la demo.
# =============================================================================

from aws_cdk import (
    Stack,
    Tags,
    CfnOutput,
    aws_iam as iam,
)
from constructs import Construct


class IamStack(Stack):
    """
    Crea recursos IAM con problemas intencionales.

    HALLAZGOS ESPERADOS (Security):
    - [CRITICAL] Usuario 'iam-user-no-mfa' sin MFA habilitado (con acceso consola)
    - [CRITICAL] Usuario 'iam-user-old-key' con access key de más de 90 días
    - [HIGH]     Usuario 'iam-user-inactive' sin actividad en 90+ días
    - [HIGH]     Política 'policy-permissive' con permisos *:* adjunta a usuario
    - [CRITICAL] Usuario 'iam-user-admin-direct' con AdministratorAccess directo
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # Grupo IAM para desarrolladores (bien configurado como referencia)
        # ---------------------------------------------------------------
        dev_group = iam.Group(
            self,
            "DevGroup",
            group_name="developers",
        )
        dev_group.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("ReadOnlyAccess")
        )

        # ---------------------------------------------------------------
        # Usuario #1 — Sin MFA (Security: CRITICAL)
        # Tiene acceso a consola pero sin MFA habilitado
        # ---------------------------------------------------------------
        user_no_mfa = iam.User(
            self,
            "UserNoMfa",
            user_name="iam-user-no-mfa",
            groups=[dev_group],
            # password_reset_required=True pero SIN MFA — hallazgo CRITICAL
        )
        Tags.of(user_no_mfa).add("Owner",       "devops@acme-corp.com")
        Tags.of(user_no_mfa).add("Department",  "Engineering")
        Tags.of(user_no_mfa).add("Note",        "Sin MFA - hallazgo CGA critical")

        # ---------------------------------------------------------------
        # Usuario #2 — Access key antigua (Security: HIGH)
        # Simula un usuario de servicio cuya key nunca fue rotada
        # ---------------------------------------------------------------
        user_old_key = iam.User(
            self,
            "UserOldKey",
            user_name="iam-user-svc-integration",
            groups=[dev_group],
        )

        # Access key creada — simulará tener más de 90 días en el reporte
        # (en una cuenta nueva, el CGA verifica la fecha de creación de la key)
        user_old_key_access = iam.CfnAccessKey(
            self,
            "UserOldKeyAccessKey",
            user_name=user_old_key.user_name,
            status="Active",
        )

        Tags.of(user_old_key).add("Owner",      "integrations@acme-corp.com")
        Tags.of(user_old_key).add("Department", "Engineering")
        Tags.of(user_old_key).add("Note",       "Access key sin rotar - hallazgo CGA high")

        # ---------------------------------------------------------------
        # Usuario #3 — Inactivo 90+ días (Security: HIGH)
        # Simula una cuenta de ex-empleado no desactivada
        # ---------------------------------------------------------------
        user_inactive = iam.User(
            self,
            "UserInactive",
            user_name="iam-user-ex-employee",
            groups=[dev_group],
        )
        Tags.of(user_inactive).add("Owner",      "hr@acme-corp.com")
        Tags.of(user_inactive).add("Department", "HR")
        Tags.of(user_inactive).add("Note",       "Usuario inactivo ex-empleado - hallazgo CGA high")

        # ---------------------------------------------------------------
        # Usuario #4 — Con política permisiva *:* (Security: HIGH)
        # Simula un usuario de emergencia que quedó con acceso total
        # ---------------------------------------------------------------
        user_permissive = iam.User(
            self,
            "UserPermissive",
            user_name="iam-user-emergency",
        )

        # Política con permisos excesivos — hallazgo HIGH
        policy_permissive = iam.Policy(
            self,
            "PolicyPermissive",
            policy_name="policy-emergency-full-access",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["*"],       # Permiso * — INSEGURO
                    resources=["*"],     # Todos los recursos — INSEGURO
                )
            ],
        )
        policy_permissive.attach_to_user(user_permissive)
        Tags.of(user_permissive).add("Owner",      "security@acme-corp.com")
        Tags.of(user_permissive).add("Department", "Security")
        Tags.of(user_permissive).add("Note",       "Usuario con politica asterisco - hallazgo CGA high")

        # ---------------------------------------------------------------
        # Usuario #5 — AdministratorAccess directo (Security: CRITICAL)
        # Simula un desarrollador al que se le dio acceso total "temporalmente"
        # ---------------------------------------------------------------
        user_admin = iam.User(
            self,
            "UserAdminDirect",
            user_name="iam-user-dev-admin",
        )
        user_admin.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )
        Tags.of(user_admin).add("Owner",      "cto@acme-corp.com")
        Tags.of(user_admin).add("Department", "Engineering")
        Tags.of(user_admin).add("Note",       "AdministratorAccess directo temporal - hallazgo CGA critical")

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "UserNoMfaArn",       value=user_no_mfa.user_arn,    export_name="SampleUserNoMfaArn")
        CfnOutput(self, "UserOldKeyArn",      value=user_old_key.user_arn,   export_name="SampleUserOldKeyArn")
        CfnOutput(self, "UserInactiveArn",    value=user_inactive.user_arn,  export_name="SampleUserInactiveArn")
        CfnOutput(self, "UserPermissiveArn",  value=user_permissive.user_arn,export_name="SampleUserPermissiveArn")
        CfnOutput(self, "UserAdminArn",       value=user_admin.user_arn,     export_name="SampleUserAdminArn")
        CfnOutput(self, "OldKeyId",           value=user_old_key_access.ref, export_name="SampleOldKeyId")
