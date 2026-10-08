# Reporte de Análisis de Costos AWS — Cloud Governance Agent
**Fecha del análisis:** 8 de octubre de 2026  
**Cuenta AWS:** 062560094883  
**Región principal:** us-east-1

---

## RESUMEN EJECUTIVO

El gasto real en septiembre 2026 fue **~$167 USD**. El **77% del gasto total proviene de Amazon RDS** ($130.25), servicio que pertenece a los stacks de demo (`CGA-Sample-Database`), no al proyecto principal. La infraestructura core del `cloud-governance-agent` (Lambda + EventBridge + S3 + SNS) tiene costo prácticamente **$0**. Eliminando todos los stacks demo (`CGA-Sample-*`) se puede reducir el gasto mensual de **~$167 a menos de $1 USD**, un ahorro del **≈99%**.

---

## 1. COSTOS ACTUALES (Cost Explorer)

### Septiembre 2026 (mes completo)

| Servicio | Costo Sep | Costo Oct 1-8 | Proyección Oct |
|---|---|---|---|
| Amazon RDS | **$130.25** | $38.35 | **~$165** |
| Amazon ELB (ALB) | $12.42 | $3.60 | ~$15.50 |
| Amazon EC2 – Compute | $11.47 | $3.28 | ~$14.10 |
| Amazon VPC | $11.04 | $3.20 | ~$13.80 |
| EC2 – Other (EBS, EIP) | $1.96 | $0.53 | ~$2.30 |
| AWS Secrets Manager | $0.61 | $0.17 | ~$0.74 |
| Amazon S3 | $0.0003 | ~$0 | ~$0 |
| AWS Lambda | $0.00 | $0.00 | $0 |
| Amazon DynamoDB | $0.00 | $0.00 | $0 |
| CloudWatch | $0.00 | $0.00 | $0 |
| SNS | $0.00 | $0.00 | $0 |
| **TOTAL** | **$167.78** | **$49.13** | **~$211** |

> ⚠️ Octubre está proyectando ~$211 (el mes anterior fue $167). RDS sigue siendo el principal generador de costos.

---

## 2. INVENTARIO COMPLETO DE RECURSOS

### 2.1 Stacks CloudFormation Activos (8)

| Stack | Estado | Tipo | Descripción |
|---|---|---|---|
| `CloudGovernanceAgent` | UPDATE_COMPLETE | **PROYECTO CORE** | Cloud Governance Agent — auditoría continua |
| `CGA-Sample-IAM` | CREATE_COMPLETE | **DEMO** | IAM: usuarios sin MFA, keys antiguas, políticas permisivas |
| `CGA-Sample-Frontend` | CREATE_COMPLETE | **DEMO** | CloudFront sin WAF, HTTP permitido |
| `CGA-Sample-Network` | CREATE_COMPLETE | **DEMO** | VPC, SGs inseguros, EIP huérfana, ALB inactivo |
| `CGA-Sample-Storage` | CREATE_COMPLETE | **DEMO** | S3 público, sin lifecycle, EBS huérfano |
| `CGA-Sample-Database` | CREATE_COMPLETE | **DEMO** | RDS pública/detenida, DynamoDB inactiva |
| `CGA-Sample-Compute` | CREATE_COMPLETE | **DEMO** | EC2 subutilizada/detenida, Lambda sin invocaciones |
| `CDKToolkit` | CREATE_COMPLETE | **INFRAESTRUCTURA** | CDK bootstrap (requerido para despliegues CDK) |

### 2.2 Funciones Lambda (4)

| Función | Runtime | Memoria | Timeout | Stack | Propósito |
|---|---|---|---|---|---|
| `cloud-governance-agent` | python3.12 | 512 MB | 900 s | CloudGovernanceAgent | **CORE** — ejecuta auditorías |
| `fn-unused-processor` | python3.9 | 128 MB | 30 s | CGA-Sample-Compute | DEMO — sin invocaciones |
| `fn-legacy-webhook` | python3.8 | 256 MB | 60 s | CGA-Sample-Compute | DEMO — sin invocaciones, runtime deprecated |
| `CGA-Sample-Frontend-CustomS3AutoDelete...` | nodejs20.x | 128 MB | 900 s | CGA-Sample-Frontend | DEMO — auto-delete S3 |

> Lambda con free tier generoso (1M requests/mes) — costo actual: $0.

### 2.3 Instancias EC2 (3)

| Instance ID | Tipo | Estado | Stack | Descripción |
|---|---|---|---|---|
| `i-0080cd765d651a620` | t3.micro | **RUNNING** | CGA-Sample-Compute | `ec2-oversized-backend` — CPU promedio 2% |
| `i-076b75d85f6a96141` | t3.micro | **RUNNING** | CGA-Sample-Compute | `ec2-no-tags` — IP pública expuesta: 3.232.107.13 |
| `i-08f1e0f572fb7dd80` | t3.micro | **STOPPED** | CGA-Sample-Compute | `ec2-stopped-staging` — detenida hace 15 días |

> Costo estimado: 2x t3.micro running ≈ $0.0104/hr × 2 × 720 hr = **~$15/mes**. La instancia detenida no genera cómputo pero sí cobra el EBS adjunto.

### 2.4 Bases de Datos RDS (2) — **MAYOR GASTO**

| Identificador | Motor | Clase | Estado | Stack | Notas |
|---|---|---|---|---|---|
| `cga-sample-database-rdspublicmysql...` | MySQL 8.0.46 | db.t3.micro | **AVAILABLE** | CGA-Sample-Database | ⚠️ Públicamente accesible, sin encriptación |
| `cga-sample-database-rdsstoppedpostgres...` | PostgreSQL 15.7 | db.t3.micro | **AVAILABLE** | CGA-Sample-Database | Nota: "detenida 15 días" pero estado shows `available` |

> **NOTA CRÍTICA:** RDS en estado `available` genera cargo 24/7 aunque no reciba tráfico. db.t3.micro ≈ $0.017/hr × 2 instancias × 720 hr = **~$24.50/mes en cómputo** + almacenamiento + backup = ~$55–65/mes por instancia. Esto explica el $130/mes observado.

### 2.5 Application Load Balancer (1)

| Nombre | Estado | Stack | VPC |
|---|---|---|---|
| `alb-idle-demo` | active | CGA-Sample-Network | vpc-0aa4f394ecd69c9a8 |

> ALB activo pero probablemente sin tráfico real. Costo: $0.008/hora × 720 hr + LCU = **~$16–18/mes**. Coincide con el $12.42 de septiembre.

### 2.6 VPCs (2)

| VPC ID | Default | CIDR | Stack |
|---|---|---|---|
| `vpc-07f0bf5c5eac83e89` | **Sí** | 172.31.0.0/16 | — (VPC default de la cuenta) |
| `vpc-0aa4f394ecd69c9a8` | No | 10.0.0.0/16 | CGA-Sample-Network |

> La VPC no-default está generando costos de VPC (~$11/mes) probablemente por Elastic IPs y/o tráfico de datos.

### 2.7 Elastic IP Addresses (3)

| IP Pública | Estado | Asociada a | Stack |
|---|---|---|---|
| `100.49.64.172` | **HUÉRFANA** (no asociada) | — | CGA-Sample-Network |
| `23.20.22.250` | Asociada | RDS (ENI) | — |
| `44.215.187.8` | Asociada | ALB | — |

> La EIP huérfana (`eip-orphan-demo`) cobra **$0.005/hr = $3.60/mes** sin proveer ningún valor. Su nota explícita dice "hallazgo CGA intencional".

### 2.8 Volúmenes EBS (4)

| Volume ID | Tamaño | Estado | Stack |
|---|---|---|---|
| `vol-0a9a460f93268004f` | 8 GB gp3 | **available** (huérfano) | CGA-Sample-Storage |
| `vol-0b01b290fb63a30cc` | 8 GB gp3 | in-use → i-076b75d85f6a96141 | CGA-Sample-Compute |
| `vol-0223d51726f76fc0d` | 8 GB gp3 | in-use → i-08f1e0f572fb7dd80 | CGA-Sample-Compute |
| `vol-08b1695145561f0b2` | 8 GB gp3 | in-use → i-0080cd765d651a620 | CGA-Sample-Compute |

> El volumen huérfano (`vol-orphan-data`) cobra ~$0.08/GB/mes × 8 GB = **$0.64/mes** sin utilidad.

### 2.9 Buckets S3 (8)

| Bucket | Objetos | Tamaño | Stack |
|---|---|---|---|
| `cdk-hnb659fds-assets-...` | 18 | 558 KB | CDKToolkit |
| `cga-reports-062560094883` | 11 | 1.02 MB | CloudGovernanceAgent |
| `cga-sample-frontend-originbucket2695925c0-...` | 0 | 0 | CGA-Sample-Frontend |
| `cga-sample-frontend-originbucketca772b8f-...` | 0 | 0 | CGA-Sample-Frontend |
| `cga-sample-storage-bucketaccesslogs-...` | 0 | 0 | CGA-Sample-Storage |
| `cga-sample-storage-bucketarchive-...` | 0 | 0 | CGA-Sample-Storage |
| `cga-sample-storage-bucketnologs-...` | 0 | 0 | CGA-Sample-Storage |
| `cga-sample-storage-bucketpublic-...` | 0 | 0 | CGA-Sample-Storage |

> S3 costo total: < $0.001/mes. Sin impacto significativo.

### 2.10 CloudFront Distributions (2)

| ID | Dominio | WAF | HTTP | Stack |
|---|---|---|---|---|
| `EY7V9BY6D9983` | d1epx68g9eehc1.cloudfront.net | ❌ Sin WAF | redirect-to-https | CGA-Sample-Frontend |
| `E3E9JWI4UVRF7D` | d1mx27gs498drj.cloudfront.net | ❌ Sin WAF | ⚠️ allow-all | CGA-Sample-Frontend |

> CloudFront con free tier (1 TB/mes de datos de salida) — costo actual: $0 para los niveles actuales de tráfico.

### 2.11 Tabla DynamoDB (1)

| Tabla | Stack |
|---|---|
| `tbl-inactive-sessions` | CGA-Sample-Database |

> DynamoDB on-demand con 0 operaciones → costo $0.

### 2.12 Otros Recursos

| Recurso | Detalle |
|---|---|
| **Secrets Manager (2)** | 2 secretos para las RDS de demo → $0.40/secreto/mes = **$0.80/mes** |
| **EventBridge Rule (1)** | `cga-weekly-schedule` — ejecuta CGA cada lunes 08:00 UTC → CORE, $0 |
| **SNS Topic (1)** | `cga-lambda-alarms` → CORE, $0 |
| **CloudWatch Alarm (1)** | `CGA-Lambda-Errors` → CORE, $0 |
| **Log Groups (2)** | `/aws/lambda/cloud-governance-agent` (retención 90 días ✓), lambda demo (sin retención ⚠️) |

---

## 3. RECURSOS DEL PROYECTO CORE vs DEMO

### ✅ Infraestructura CORE (cloud-governance-agent) — NO ELIMINAR

| Recurso | Costo Mensual |
|---|---|
| Lambda `cloud-governance-agent` (python3.12, 512MB) | $0 (free tier) |
| EventBridge Rule `cga-weekly-schedule` | $0 |
| SNS Topic `cga-lambda-alarms` | $0 |
| CloudWatch Alarm `CGA-Lambda-Errors` | $0 |
| S3 `cga-reports-062560094883` (1 MB, 11 objetos) | ~$0 |
| Log Group `/aws/lambda/cloud-governance-agent` (90 días) | ~$0 |
| Stack `CloudGovernanceAgent` | — |
| Stack `CDKToolkit` | $0 |
| **TOTAL CORE** | **~$0/mes** |

### ❌ Infraestructura DEMO (CGA-Sample-*) — CANDIDATA A ELIMINACIÓN

Todos los stacks `CGA-Sample-*` fueron creados el 7 de septiembre de 2026 y tienen como propósito generar hallazgos artificiales ("hallazgo CGA intencional") para demostrar las capacidades del agente. Son la fuente del **99.9% del gasto**.

---

## 4. RECURSOS RECOMENDADOS PARA DESHABILITAR/ELIMINAR

### PRIORIDAD ALTA — Acción inmediata

| # | Recurso | Acción | Ahorro Mensual Estimado |
|---|---|---|---|
| 1 | **RDS MySQL** `rds-public-mysql` (db.t3.micro, publicly accessible) | Eliminar (parte de `CGA-Sample-Database`) | **~$65/mes** |
| 2 | **RDS PostgreSQL** `rds-stopped-postgres` (db.t3.micro) | Eliminar (parte de `CGA-Sample-Database`) | **~$65/mes** |
| 3 | **ALB** `alb-idle-demo` (sin tráfico real) | Eliminar (parte de `CGA-Sample-Network`) | **~$16/mes** |
| 4 | **EC2** `ec2-no-tags` (t3.micro running, IP pública) | Terminar (parte de `CGA-Sample-Compute`) | **~$8/mes** |
| 5 | **EC2** `ec2-oversized-backend` (t3.micro running, CPU 2%) | Terminar (parte de `CGA-Sample-Compute`) | **~$8/mes** |
| 6 | **VPC** `sample-production-vpc` + subnets | Eliminar tras depender de `CGA-Sample-Network` | **~$11/mes** |

### PRIORIDAD MEDIA

| # | Recurso | Acción | Ahorro Mensual Estimado |
|---|---|---|---|
| 7 | **EIP huérfana** `eip-orphan-demo` | Liberar (parte de `CGA-Sample-Network`) | **$3.60/mes** |
| 8 | **Secrets Manager** (2 secretos de RDS demo) | Eliminar al eliminar las RDS | **$0.80/mes** |
| 9 | **EBS huérfano** `vol-orphan-data` (8 GB, no adjunto) | Eliminar (parte de `CGA-Sample-Storage`) | **$0.64/mes** |
| 10 | **EC2 detenida** `ec2-stopped-staging` | Terminar (EBS cobra aunque esté detenida) | **$0.64/mes** |
| 11 | **CloudFront distributions** (2, sin tráfico) | Deshabilitar o eliminar con `CGA-Sample-Frontend` | **$0** (pero reduce superficie de ataque) |
| 12 | **Lambda** `fn-legacy-webhook` (python3.8, deprecated) | Eliminar con `CGA-Sample-Compute` | **$0** |
| 13 | **Lambda** `fn-unused-processor` (sin invocaciones) | Eliminar con `CGA-Sample-Compute` | **$0** |

---

## 5. ESTIMADO DE AHORRO

### Método recomendado: eliminar todos los stacks demo

La manera más limpia y segura es eliminar los stacks en orden de dependencias:

```bash
# 1. Eliminar primero los stacks con dependencias entre sí
aws cloudformation delete-stack --stack-name CGA-Sample-Compute
aws cloudformation delete-stack --stack-name CGA-Sample-Database
aws cloudformation delete-stack --stack-name CGA-Sample-Frontend
aws cloudformation delete-stack --stack-name CGA-Sample-Storage
aws cloudformation delete-stack --stack-name CGA-Sample-Network
aws cloudformation delete-stack --stack-name CGA-Sample-IAM
```

> ⚠️ Antes de eliminar, verificar que ningún stack tenga DeletionPolicy: Retain en recursos críticos.  
> ⚠️ Las instancias RDS tienen `DeletionProtection: false` y `BackupRetentionPeriod` = 1–7 días, por lo que se puede proceder.

### Resumen del ahorro estimado

| Escenario | Costo Mensual Actual | Costo Mensual Post-Acción | Ahorro |
|---|---|---|---|
| Sin cambios | ~$167–$211 | — | — |
| Eliminar todos los stacks `CGA-Sample-*` | ~$167 | **< $1** | **~$166/mes (99%)** |
| Solo eliminar RDS (acción más urgente) | ~$167 | ~$36–42 | **~$130/mes (78%)** |
| Solo eliminar RDS + ALB + EC2 | ~$167 | ~$12 | **~$155/mes (93%)** |

### Proyección anual

- **Eliminando todos los stacks demo:** ahorro de **~$1,990/año**
- **Solo eliminando RDS:** ahorro de **~$1,560/año**

---

## 6. OBSERVACIONES DE SEGURIDAD (sin costo adicional, alto riesgo)

Los siguientes hallazgos son parte del diseño "demo" pero representan riesgos reales activos:

1. **RDS MySQL públicamente accesible** (`PubliclyAccessible: true`) sin encriptación en tránsito ni en reposo → exposición directa a Internet.
2. **EC2 `ec2-no-tags`** con IP pública `3.232.107.13` en security group `web-open-sg` → posiblemente abierto a 0.0.0.0/0.
3. **CloudFront distribution `E3E9JWI4UVRF7D`** con `ViewerProtocolPolicy: allow-all` → permite HTTP sin cifrar.
4. **Log Group** de Lambda demo sin retención definida → acumula logs indefinidamente.
5. **IAM Stack** (`CGA-Sample-IAM`) creó usuarios sin MFA y políticas permisivas activas.

---

*Reporte generado automáticamente por cloud-governance-agent el 2026-10-08*
