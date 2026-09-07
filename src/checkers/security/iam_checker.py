"""
iam_checker.py — Auditoría de seguridad de AWS IAM.

Checks implementados:
  - [CRITICAL] Usuarios sin MFA habilitado
  - [HIGH]     Access keys sin rotación +90 días
  - [HIGH]     Usuarios inactivos 90+ días
  - [HIGH]     Políticas con permisos *:* adjuntas directamente a usuarios
  - [CRITICAL] Usuarios con AdministratorAccess adjunto directamente
"""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory


class IAMChecker(BaseChecker):
    """Audita configuraciones de seguridad de usuarios y políticas IAM."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.iam = factory.get_client("iam")
        self.key_age_threshold = int(config.get("key_age_days_threshold", 90))
        self.inactive_threshold = int(config.get("inactive_days_threshold", 90))

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de IAM y retorna hallazgos."""
        self.logger.info("Iniciando IAMChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []

        try:
            users = self._list_all_users()
            credential_report = self._get_credential_report()

            for user in users:
                username = user["UserName"]
                user_arn = user["Arn"]
                tags = self._extract_tags(user.get("Tags", []))

                findings.extend(self._check_mfa(user, tags, credential_report))
                findings.extend(self._check_access_keys(user, tags))
                findings.extend(self._check_inactive_user(user, tags, credential_report))
                findings.extend(self._check_permissive_policies(user, tags))

        except Exception as e:
            self.logger.error("Error en IAMChecker", extra={"error": str(e)})

        self.logger.info(
            "IAMChecker completado",
            extra={"findings": len(findings), "account_id": self.account_id},
        )
        return findings

    # ------------------------------------------------------------------
    # Check 1: Usuarios sin MFA
    # ------------------------------------------------------------------
    def _check_mfa(
        self,
        user: Dict,
        tags: Dict[str, str],
        credential_report: Dict[str, Dict],
    ) -> List[Finding]:
        findings = []
        username = user["UserName"]
        user_arn = user["Arn"]

        try:
            # Verificar si tiene login profile (acceso a consola)
            has_console = False
            try:
                self.iam.get_login_profile(UserName=username)
                has_console = True
            except self.iam.exceptions.NoSuchEntityException:
                pass

            if not has_console:
                return []  # Sin acceso a consola, MFA no aplica

            # Verificar MFA en credential report
            report_row = credential_report.get(username, {})
            mfa_active = report_row.get("mfa_active", "false").lower() == "true"

            if not mfa_active:
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="iam",
                        severity="critical",
                        resource_id=user_arn,
                        resource_type="AWS::IAM::User",
                        region="global",
                        title=f"Usuario IAM sin MFA: {username}",
                        description=(
                            f"El usuario '{username}' tiene acceso a la consola AWS "
                            f"pero no tiene MFA (Multi-Factor Authentication) habilitado. "
                            f"Si las credenciales son comprometidas, el atacante tendría "
                            f"acceso completo sin ninguna barrera adicional."
                        ),
                        recommendation=(
                            "Habilitar MFA inmediatamente: IAM → Users → "
                            f"{username} → Security credentials → Assign MFA device. "
                            "Considerar uso de MFA virtual (Google Authenticator) o hardware (YubiKey)."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={
                            "user_name": username,
                            "has_console_access": True,
                            "mfa_active": False,
                            "password_last_used": report_row.get("password_last_used", "N/A"),
                        },
                    )
                )
        except Exception as e:
            self.logger.warning(
                "Error verificando MFA",
                extra={"user": username, "error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Check 2: Access keys sin rotación
    # ------------------------------------------------------------------
    def _check_access_keys(
        self, user: Dict, tags: Dict[str, str]
    ) -> List[Finding]:
        findings = []
        username = user["UserName"]
        user_arn = user["Arn"]

        try:
            paginator = self.iam.get_paginator("list_access_keys")
            for page in paginator.paginate(UserName=username):
                for key in page.get("AccessKeyMetadata", []):
                    if key["Status"] != "Active":
                        continue

                    created = key["CreateDate"]
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)

                    age_days = (datetime.now(timezone.utc) - created).days

                    if age_days >= self.key_age_threshold:
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="iam",
                                severity="high",
                                resource_id=user_arn,
                                resource_type="AWS::IAM::AccessKey",
                                region="global",
                                title=f"Access key sin rotación {age_days} días: {username}",
                                description=(
                                    f"El usuario '{username}' tiene una access key activa "
                                    f"(ID: ...{key['AccessKeyId'][-4:]}) creada hace "
                                    f"{age_days} días sin ser rotada. Las keys antiguas "
                                    f"aumentan el riesgo de exposición si fueron comprometidas."
                                ),
                                recommendation=(
                                    f"Rotar la access key: crear una nueva key, actualizar "
                                    f"las aplicaciones que la usan, y desactivar/eliminar la antigua. "
                                    f"Política recomendada: rotación cada {self.key_age_threshold} días."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={
                                    "user_name": username,
                                    "access_key_id_suffix": key["AccessKeyId"][-4:],
                                    "key_age_days": age_days,
                                    "threshold_days": self.key_age_threshold,
                                    "created_date": created.isoformat(),
                                    "status": key["Status"],
                                },
                            )
                        )
        except Exception as e:
            self.logger.warning(
                "Error verificando access keys",
                extra={"user": username, "error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Check 3: Usuarios inactivos
    # ------------------------------------------------------------------
    def _check_inactive_user(
        self,
        user: Dict,
        tags: Dict[str, str],
        credential_report: Dict[str, Dict],
    ) -> List[Finding]:
        findings = []
        username = user["UserName"]
        user_arn = user["Arn"]

        try:
            report_row = credential_report.get(username, {})
            password_last_used = report_row.get("password_last_used", "no_information")
            key1_last_used = report_row.get("access_key_1_last_used_date", "N/A")
            key2_last_used = report_row.get("access_key_2_last_used_date", "N/A")

            # Determinar la fecha de última actividad
            last_activity: Optional[datetime] = None
            for date_str in [password_last_used, key1_last_used, key2_last_used]:
                if date_str and date_str not in ("N/A", "no_information", ""):
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        if last_activity is None or dt > last_activity:
                            last_activity = dt
                    except ValueError:
                        pass

            if last_activity is None:
                # Sin actividad registrada — usuario nunca usado
                inactive_days = self.inactive_threshold + 1
                last_activity_str = "Nunca"
            else:
                inactive_days = (datetime.now(timezone.utc) - last_activity).days
                last_activity_str = last_activity.isoformat()

            if inactive_days >= self.inactive_threshold:
                findings.append(
                    self._build_finding(
                        domain="security",
                        category="iam",
                        severity="high",
                        resource_id=user_arn,
                        resource_type="AWS::IAM::User",
                        region="global",
                        title=f"Usuario IAM inactivo {inactive_days}+ días: {username}",
                        description=(
                            f"El usuario '{username}' no ha tenido actividad en los "
                            f"últimos {inactive_days} días (última actividad: {last_activity_str}). "
                            f"Los usuarios inactivos representan un riesgo de seguridad latente "
                            f"si sus credenciales son comprometidas."
                        ),
                        recommendation=(
                            f"Verificar si el usuario '{username}' sigue siendo necesario. "
                            f"Si pertenece a un ex-empleado o servicio descontinuado, "
                            f"desactivar o eliminar inmediatamente."
                        ),
                        owner=self._get_tag(tags, "owner"),
                        project=self._get_tag(tags, "project"),
                        environment=self._get_tag(tags, "environment"),
                        cost_center=self._get_tag(tags, "costcenter"),
                        evidence={
                            "user_name": username,
                            "inactive_days": inactive_days,
                            "threshold_days": self.inactive_threshold,
                            "last_activity": last_activity_str,
                            "password_last_used": password_last_used,
                            "key1_last_used": key1_last_used,
                            "key2_last_used": key2_last_used,
                        },
                    )
                )
        except Exception as e:
            self.logger.warning(
                "Error verificando inactividad",
                extra={"user": username, "error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Check 4: Políticas permisivas *:*
    # ------------------------------------------------------------------
    def _check_permissive_policies(
        self, user: Dict, tags: Dict[str, str]
    ) -> List[Finding]:
        findings = []
        username = user["UserName"]
        user_arn = user["Arn"]

        try:
            # Políticas administradas adjuntas directamente
            paginator = self.iam.get_paginator("list_attached_user_policies")
            for page in paginator.paginate(UserName=username):
                for policy in page.get("AttachedPolicies", []):
                    policy_name = policy["PolicyName"]
                    policy_arn  = policy["PolicyArn"]

                    # AdministratorAccess — siempre es CRITICAL
                    if policy_name == "AdministratorAccess":
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="iam",
                                severity="critical",
                                resource_id=user_arn,
                                resource_type="AWS::IAM::User",
                                region="global",
                                title=f"AdministratorAccess directo en usuario: {username}",
                                description=(
                                    f"El usuario '{username}' tiene la política "
                                    f"'AdministratorAccess' adjunta directamente, otorgando "
                                    f"acceso total a todos los servicios y recursos AWS. "
                                    f"Viola el principio de mínimo privilegio."
                                ),
                                recommendation=(
                                    "Revocar AdministratorAccess del usuario. Asignar solo "
                                    "los permisos necesarios para su función. Si se requiere "
                                    "acceso administrativo temporal, usar roles IAM con "
                                    "AssumeRole y sesiones con tiempo limitado."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={
                                    "user_name": username,
                                    "policy_name": policy_name,
                                    "policy_arn": policy_arn,
                                },
                            )
                        )
                        continue

                    # Verificar si la política tiene Allow *:*
                    if self._policy_has_wildcard(policy_arn):
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="iam",
                                severity="high",
                                resource_id=user_arn,
                                resource_type="AWS::IAM::Policy",
                                region="global",
                                title=f"Política con permisos '*:*' en usuario: {username}",
                                description=(
                                    f"La política '{policy_name}' adjunta al usuario "
                                    f"'{username}' contiene permisos con Action='*' y "
                                    f"Resource='*', otorgando acceso ilimitado. "
                                    f"Viola el principio de mínimo privilegio."
                                ),
                                recommendation=(
                                    f"Revisar y reemplazar la política '{policy_name}' por "
                                    f"una con permisos específicos al rol del usuario. "
                                    f"Usar el IAM Access Analyzer para identificar permisos "
                                    f"realmente utilizados."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={
                                    "user_name": username,
                                    "policy_name": policy_name,
                                    "policy_arn": policy_arn,
                                },
                            )
                        )

            # Políticas inline
            paginator2 = self.iam.get_paginator("list_user_policies")
            for page in paginator2.paginate(UserName=username):
                for policy_name in page.get("PolicyNames", []):
                    policy_doc = self.iam.get_user_policy(
                        UserName=username, PolicyName=policy_name
                    )
                    if self._document_has_wildcard(
                        policy_doc.get("PolicyDocument", {})
                    ):
                        findings.append(
                            self._build_finding(
                                domain="security",
                                category="iam",
                                severity="high",
                                resource_id=user_arn,
                                resource_type="AWS::IAM::Policy",
                                region="global",
                                title=f"Política inline con '*:*' en usuario: {username}",
                                description=(
                                    f"La política inline '{policy_name}' del usuario "
                                    f"'{username}' contiene permisos comodín (*). "
                                    f"Las políticas inline con acceso total son difíciles "
                                    f"de auditar y violan mínimo privilegio."
                                ),
                                recommendation=(
                                    f"Eliminar la política inline '{policy_name}' y "
                                    f"reemplazarla por una política administrada con "
                                    f"permisos específicos."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={
                                    "user_name": username,
                                    "policy_name": policy_name,
                                    "policy_type": "inline",
                                },
                            )
                        )

        except Exception as e:
            self.logger.warning(
                "Error verificando políticas",
                extra={"user": username, "error": str(e)},
            )

        return findings

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _list_all_users(self) -> List[Dict]:
        """Lista todos los usuarios IAM con sus tags."""
        users = []
        paginator = self.iam.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page.get("Users", []):
                # Obtener tags del usuario
                try:
                    tags_resp = self.iam.list_user_tags(UserName=user["UserName"])
                    user["Tags"] = tags_resp.get("Tags", [])
                except Exception:
                    user["Tags"] = []
                users.append(user)
        return users

    def _get_credential_report(self) -> Dict[str, Dict]:
        """Genera y retorna el credential report de IAM como dict."""
        try:
            # Generar el reporte (puede tardar unos segundos)
            for _ in range(10):
                resp = self.iam.generate_credential_report()
                if resp.get("State") == "COMPLETE":
                    break
                time.sleep(2)

            report = self.iam.get_credential_report()
            content = report["Content"].decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            return {row["user"]: row for row in reader}
        except Exception as e:
            self.logger.warning(
                "No se pudo obtener credential report",
                extra={"error": str(e)},
            )
            return {}

    def _policy_has_wildcard(self, policy_arn: str) -> bool:
        """Verifica si una política administrada tiene Allow *:*."""
        try:
            policy = self.iam.get_policy(PolicyArn=policy_arn)
            version_id = policy["Policy"]["DefaultVersionId"]
            version = self.iam.get_policy_version(
                PolicyArn=policy_arn, VersionId=version_id
            )
            doc = version["PolicyVersion"]["Document"]
            return self._document_has_wildcard(doc)
        except Exception:
            return False

    def _document_has_wildcard(self, document: Dict) -> bool:
        """Verifica si un documento de política contiene Allow con Action=* y Resource=*."""
        statements = document.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]
        for stmt in statements:
            if stmt.get("Effect") != "Allow":
                continue
            actions   = stmt.get("Action", [])
            resources = stmt.get("Resource", [])
            if isinstance(actions, str):
                actions = [actions]
            if isinstance(resources, str):
                resources = [resources]
            if "*" in actions and "*" in resources:
                return True
        return False
