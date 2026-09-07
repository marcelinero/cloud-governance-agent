"""
storage_checker.py — Auditoría FinOps de almacenamiento AWS.

Checks implementados:
  - [MEDIUM] S3 buckets sin lifecycle policy
  - [MEDIUM] Volúmenes EBS en estado 'available' (sin adjuntar) +7 días
  - [LOW]    Snapshots EBS huérfanos +30 días
  - [LOW]    AMIs no utilizadas +90 días
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from botocore.exceptions import ClientError

from src.checkers import BaseChecker
from src.core.models import Finding
from src.utils.aws_client import AWSClientFactory

# Precio por GB-mes (us-east-1)
EBS_COST_PER_GB: Dict[str, float] = {
    "gp3": 0.08, "gp2": 0.10, "io1": 0.125,
    "io2": 0.125, "st1": 0.045, "sc1": 0.025,
    "standard": 0.05,
}
S3_COST_PER_GB_MONTH = 0.023   # Standard storage
SNAPSHOT_COST_PER_GB = 0.05    # EBS snapshot


class StorageChecker(BaseChecker):
    """Detecta recursos de almacenamiento huérfanos o mal gestionados."""

    def __init__(self, factory: AWSClientFactory, config: Dict[str, Any]) -> None:
        super().__init__(factory, config)
        self.ec2            = factory.get_client("ec2")
        self.s3             = factory.get_client("s3")
        self.orphan_days    = int(config.get("stopped_days_threshold", 7))
        self.snapshot_days  = int(config.get("snapshot_age_days", 30))
        self.ami_age_days   = int(config.get("ami_age_days", 90))

    def run(self) -> List[Finding]:
        self.logger.info("Iniciando StorageChecker", extra={"account_id": self.account_id})
        findings: List[Finding] = []
        try:
            findings.extend(self._check_s3_lifecycle())
            findings.extend(self._check_orphan_ebs())
            findings.extend(self._check_orphan_snapshots())
            findings.extend(self._check_unused_amis())
        except Exception as e:
            self.logger.error("Error en StorageChecker", extra={"error": str(e)})

        self.logger.info("StorageChecker completado", extra={"findings": len(findings)})
        return findings

    # ------------------------------------------------------------------
    # Check 1: S3 sin lifecycle policy
    # ------------------------------------------------------------------
    def _check_s3_lifecycle(self) -> List[Finding]:
        findings = []
        try:
            buckets = self.s3.list_buckets().get("Buckets", [])
            for bucket in buckets:
                name = bucket["Name"]
                tags = self._get_bucket_tags(name)
                try:
                    self.s3.get_bucket_lifecycle_configuration(Bucket=name)
                    # Tiene lifecycle — OK
                except ClientError as e:
                    if e.response["Error"]["Code"] in (
                        "NoSuchLifecycleConfiguration",
                        "NoSuchBucket",
                    ):
                        findings.append(
                            self._build_finding(
                                domain="finops",
                                category="s3",
                                severity="medium",
                                resource_id=f"arn:aws:s3:::{name}",
                                resource_type="AWS::S3::Bucket",
                                region="global",
                                title=f"Bucket S3 sin lifecycle policy: {name}",
                                description=(
                                    f"El bucket '{name}' no tiene una política de ciclo "
                                    f"de vida (lifecycle policy). Sin ella, los objetos "
                                    f"se acumulan indefinidamente en la clase Standard "
                                    f"generando costos crecientes sin necesidad."
                                ),
                                recommendation=(
                                    f"Configurar una lifecycle policy en '{name}': "
                                    f"S3 → {name} → Management → Lifecycle rules → Create rule. "
                                    f"Ejemplos: mover a Glacier después de 90 días, "
                                    f"eliminar objetos expirados, transicionar a IA después de 30 días."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                evidence={"bucket_name": name, "lifecycle": "not_configured"},
                            )
                        )
        except Exception as e:
            self.logger.error("Error verificando lifecycle S3", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 2: Volúmenes EBS sin adjuntar
    # ------------------------------------------------------------------
    def _check_orphan_ebs(self) -> List[Finding]:
        findings = []
        try:
            paginator = self.ec2.get_paginator("describe_volumes")
            for page in paginator.paginate(
                Filters=[{"Name": "status", "Values": ["available"]}]
            ):
                for vol in page.get("Volumes", []):
                    vol_id    = vol["VolumeId"]
                    vol_type  = vol.get("VolumeType", "gp2")
                    size_gb   = vol.get("Size", 0)
                    tags      = self._extract_tags(vol.get("Tags", []))
                    create_dt = vol.get("CreateTime")

                    if create_dt:
                        if create_dt.tzinfo is None:
                            create_dt = create_dt.replace(tzinfo=timezone.utc)
                        age_days = (datetime.now(timezone.utc) - create_dt).days
                    else:
                        age_days = self.orphan_days + 1

                    if age_days >= self.orphan_days:
                        cost_per_gb    = EBS_COST_PER_GB.get(vol_type, 0.08)
                        monthly_cost   = round(size_gb * cost_per_gb, 2)

                        findings.append(
                            self._build_finding(
                                domain="finops",
                                category="storage",
                                severity="medium",
                                resource_id=vol_id,
                                resource_type="AWS::EC2::Volume",
                                title=f"Volumen EBS sin adjuntar {age_days} días: {vol_id}",
                                description=(
                                    f"El volumen EBS '{vol_id}' ({vol_type}, {size_gb} GB) "
                                    f"lleva {age_days} días en estado 'available' sin estar "
                                    f"adjunto a ninguna instancia. "
                                    f"Costo mensual: ${monthly_cost:.2f} USD."
                                ),
                                recommendation=(
                                    f"Si los datos no son necesarios, eliminar el volumen "
                                    f"'{vol_id}' para ahorrar ${monthly_cost:.2f} USD/mes. "
                                    f"Si se necesitan los datos, crear un snapshot antes de eliminar."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                estimated_monthly_cost=monthly_cost,
                                potential_saving=monthly_cost,
                                evidence={
                                    "volume_id":   vol_id,
                                    "volume_type": vol_type,
                                    "size_gb":     size_gb,
                                    "age_days":    age_days,
                                    "state":       "available",
                                    "az":          vol.get("AvailabilityZone"),
                                },
                            )
                        )
        except Exception as e:
            self.logger.error("Error verificando volúmenes EBS", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 3: Snapshots EBS huérfanos
    # ------------------------------------------------------------------
    def _check_orphan_snapshots(self) -> List[Finding]:
        findings = []
        try:
            paginator = self.ec2.get_paginator("describe_snapshots")
            for page in paginator.paginate(OwnerIds=["self"]):
                for snap in page.get("Snapshots", []):
                    snap_id   = snap["SnapshotId"]
                    size_gb   = snap.get("VolumeSize", 0)
                    tags      = self._extract_tags(snap.get("Tags", []))
                    start_dt  = snap.get("StartTime")

                    if start_dt:
                        if start_dt.tzinfo is None:
                            start_dt = start_dt.replace(tzinfo=timezone.utc)
                        age_days = (datetime.now(timezone.utc) - start_dt).days
                    else:
                        age_days = self.snapshot_days + 1

                    if age_days < self.snapshot_days:
                        continue

                    # Verificar si el volumen origen existe
                    vol_id = snap.get("VolumeId", "")
                    is_orphan = not self._volume_exists(vol_id)

                    if is_orphan:
                        monthly_cost = round(size_gb * SNAPSHOT_COST_PER_GB, 2)
                        findings.append(
                            self._build_finding(
                                domain="finops",
                                category="storage",
                                severity="low",
                                resource_id=snap_id,
                                resource_type="AWS::EC2::Snapshot",
                                title=f"Snapshot EBS huérfano {age_days} días: {snap_id}",
                                description=(
                                    f"El snapshot '{snap_id}' ({size_gb} GB, {age_days} días) "
                                    f"fue creado desde el volumen '{vol_id}' que ya no existe. "
                                    f"Costo mensual: ${monthly_cost:.2f} USD."
                                ),
                                recommendation=(
                                    f"Si el snapshot ya no es necesario para recuperación, "
                                    f"eliminarlo para ahorrar ${monthly_cost:.2f} USD/mes."
                                ),
                                owner=self._get_tag(tags, "owner"),
                                project=self._get_tag(tags, "project"),
                                environment=self._get_tag(tags, "environment"),
                                cost_center=self._get_tag(tags, "costcenter"),
                                estimated_monthly_cost=monthly_cost,
                                potential_saving=monthly_cost,
                                evidence={
                                    "snapshot_id":      snap_id,
                                    "size_gb":          size_gb,
                                    "age_days":         age_days,
                                    "source_volume_id": vol_id,
                                    "volume_exists":    False,
                                },
                            )
                        )
        except Exception as e:
            self.logger.error("Error verificando snapshots EBS", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Check 4: AMIs no utilizadas
    # ------------------------------------------------------------------
    def _check_unused_amis(self) -> List[Finding]:
        findings = []
        try:
            resp = self.ec2.describe_images(Owners=["self"])
            # Obtener IDs de AMIs en uso por instancias activas
            ami_in_use = self._get_amis_in_use()

            for image in resp.get("Images", []):
                ami_id   = image["ImageId"]
                ami_name = image.get("Name", ami_id)
                tags     = self._extract_tags(image.get("Tags", []))

                if ami_id in ami_in_use:
                    continue

                create_str = image.get("CreationDate", "")
                try:
                    create_dt = datetime.fromisoformat(create_str.replace("Z", "+00:00"))
                    age_days  = (datetime.now(timezone.utc) - create_dt).days
                except (ValueError, AttributeError):
                    age_days = self.ami_age_days + 1

                if age_days >= self.ami_age_days:
                    # Calcular costo de los snapshots que componen la AMI
                    snap_cost = self._estimate_ami_cost(image)
                    findings.append(
                        self._build_finding(
                            domain="finops",
                            category="storage",
                            severity="low",
                            resource_id=ami_id,
                            resource_type="AWS::EC2::Image",
                            title=f"AMI sin uso {age_days} días: {ami_name}",
                            description=(
                                f"La AMI '{ami_name}' ({ami_id}) tiene {age_days} días "
                                f"y no está siendo utilizada por ninguna instancia activa. "
                                f"Genera costo por los snapshots EBS subyacentes: "
                                f"~${snap_cost:.2f} USD/mes."
                            ),
                            recommendation=(
                                f"Si la AMI ya no es necesaria como backup o base de lanzamiento, "
                                f"deregistrarla y eliminar los snapshots asociados."
                            ),
                            owner=self._get_tag(tags, "owner"),
                            project=self._get_tag(tags, "project"),
                            environment=self._get_tag(tags, "environment"),
                            cost_center=self._get_tag(tags, "costcenter"),
                            estimated_monthly_cost=snap_cost,
                            potential_saving=snap_cost,
                            evidence={
                                "ami_id":      ami_id,
                                "ami_name":    ami_name,
                                "age_days":    age_days,
                                "in_use":      False,
                            },
                        )
                    )
        except Exception as e:
            self.logger.error("Error verificando AMIs", extra={"error": str(e)})
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_bucket_tags(self, bucket_name: str) -> Dict[str, str]:
        try:
            resp = self.s3.get_bucket_tagging(Bucket=bucket_name)
            return self._extract_tags(resp.get("TagSet", []))
        except ClientError:
            return {}

    def _volume_exists(self, vol_id: str) -> bool:
        if not vol_id:
            return False
        try:
            resp = self.ec2.describe_volumes(VolumeIds=[vol_id])
            return len(resp.get("Volumes", [])) > 0
        except ClientError:
            return False

    def _get_amis_in_use(self) -> set:
        in_use = set()
        try:
            paginator = self.ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for r in page.get("Reservations", []):
                    for i in r.get("Instances", []):
                        if i.get("ImageId"):
                            in_use.add(i["ImageId"])
        except Exception:
            pass
        return in_use

    def _estimate_ami_cost(self, image: Dict) -> float:
        total_gb = sum(
            bdm.get("Ebs", {}).get("VolumeSize", 0)
            for bdm in image.get("BlockDeviceMappings", [])
            if bdm.get("Ebs")
        )
        return round(total_gb * SNAPSHOT_COST_PER_GB, 2)
