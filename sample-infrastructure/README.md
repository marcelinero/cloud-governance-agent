# Infraestructura de Muestra — ACME Corp (CGA Demo)

> Stack CDK que simula una compañía nativa en AWS con recursos **intencionalmente mal configurados** para ser detectados por el Cloud Governance Agent (CGA).

---

## ⚠️ Advertencia

**Este stack crea recursos con vulnerabilidades y desperdicios deliberados.**
Su único propósito es demostrar las capacidades del CGA. **No usar como referencia de buenas prácticas.**

**Costo estimado:** ~$15-25 USD/día con todos los recursos activos.
**Recordar ejecutar `cdk destroy --all` al terminar la demo.**

---

## Contexto — ACME Corp

La infraestructura simula una empresa de tecnología con los problemas más comunes que un auditor de TI encuentra en compañías que crecieron rápido sin gobierno de nube:

- Recursos creados manualmente sin estándares de etiquetado
- Instancias y bases de datos sobredimensionadas o abandonadas
- Configuraciones de seguridad relajadas "temporalmente" que nunca se cerraron
- Access keys de servicio que nunca fueron rotadas
- Distribuciones de frontend sin protección WAF
- Elastic IPs y volúmenes huérfanos acumulando costo

---

## Arquitectura de la Muestra

```
┌─────────────────────────────────────────────────────────────────┐
│  ACME Corp — AWS Account (us-east-1)                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  VPC: 10.0.0.0/16  (SIN Flow Logs ⚠️)                   │   │
│  │                                                           │   │
│  │  Public Subnets                                           │   │
│  │  ┌────────────────┐  ┌────────────────────────────────┐  │   │
│  │  │  ALB idle ⚠️   │  │  EC2 ec2-no-tags ⚠️           │  │   │
│  │  │  (sin tráfico) │  │  (sin tags obligatorios)       │  │   │
│  │  └────────────────┘  └────────────────────────────────┘  │   │
│  │                                                           │   │
│  │  Public Subnets (cont.)                                  │   │
│  │  ┌────────────────┐  ┌────────────────────────────────┐  │   │
│  │  │  EC2 oversized │  │  RDS MySQL ⚠️ (pública)       │  │   │
│  │  │  CPU 2% ⚠️     │  │                                │  │   │
│  │  └────────────────┘  └────────────────────────────────┘  │   │
│  │                                                           │   │
│  │  Isolated Subnets (sin salida a internet, sin NAT GW)     │   │
│  │  ┌────────────────┐  ┌────────────────────────────────┐  │   │
│  │  │  EC2 stopped ⚠️│  │  RDS PostgreSQL ⚠️            │  │   │
│  │  │ (detenida)     │  │  (detenida)                    │  │   │
│  │  └────────────────┘  └────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Recursos globales / regionales:                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐ │
│  │ CloudFront│ │  S3 x4  │ │ IAM x5  │ │  Lambda x2        │ │
│  │  sin WAF⚠️│ │ público⚠️│ │sin MFA⚠️ │ │  sin invocaciones  │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘ │
│                                                                  │
│  Recursos huérfanos:                                             │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  EIP no asociada │  │  EBS vol-orphan  │                     │
│  │  ⚠️ FinOps LOW   │  │  ⚠️ FinOps MEDIUM│                     │
│  └──────────────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stacks Desplegados

| Stack | Descripción | Recursos |
|---|---|---|
| `CGA-Sample-Network` | VPC, SGs, EIP, ALB | VPC, 2 SGs, 1 EIP, 1 ALB |
| `CGA-Sample-Storage` | S3 buckets, EBS | 4 buckets S3, 1 volumen EBS |
| `CGA-Sample-Compute` | EC2, Lambda | 3 instancias EC2, 2 funciones Lambda |
| `CGA-Sample-Database` | RDS, DynamoDB | 2 instancias RDS, 1 tabla DynamoDB |
| `CGA-Sample-IAM` | Usuarios IAM | 5 usuarios IAM, 1 política permisiva |
| `CGA-Sample-Frontend` | CloudFront | 2 distribuciones CF, 2 buckets origen |

---

## Prerequisitos

```bash
# 1. Python 3.12+ y entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias CDK
pip install -r requirements.txt

# 3. AWS CLI configurado
aws sts get-caller-identity

# 4. CDK instalado
npm install -g aws-cdk
cdk --version
```

---

## Despliegue

```bash
cd sample-infrastructure

# Bootstrap (solo primera vez)
cdk bootstrap aws://123456789012/us-east-1

# Ver los stacks que se van a crear
cdk list

# Desplegar todos los stacks en orden
cdk deploy --all --require-approval never

# O desplegar stack por stack
cdk deploy CGA-Sample-Network
cdk deploy CGA-Sample-Storage
cdk deploy CGA-Sample-Compute
cdk deploy CGA-Sample-Database
cdk deploy CGA-Sample-IAM
cdk deploy CGA-Sample-Frontend
```

> **Nota:** El despliegue completo toma aproximadamente 25-35 minutos debido a la creación de instancias RDS y distribuciones CloudFront.

---

## Limpieza (Destruir la Muestra)

```bash
# Destruir todos los stacks y recursos (evita costos continuos)
cdk destroy --all --force
```

> **Importante:** CloudFront puede tardar 10-15 minutos en eliminarse. Los buckets S3 se eliminan automáticamente (RemovalPolicy.DESTROY).

---

## Tabla Completa de Hallazgos Esperados

A continuación el inventario de todos los problemas intencionales que el CGA debe detectar al ejecutarse sobre esta infraestructura.

### 🔴 CRITICAL (7 hallazgos)

| # | Dominio | Recurso | Hallazgo | Stack |
|---|---|---|---|---|
| 1 | Security | `web-open-sg` | Puerto SSH (22) abierto a 0.0.0.0/0 | Network |
| 2 | Security | `db-open-sg` | Puerto MySQL (3306) abierto a 0.0.0.0/0 | Network |
| 3 | Security | `db-open-sg` | Puerto PostgreSQL (5432) abierto a 0.0.0.0/0 | Network |
| 4 | Security | `db-open-sg` | Puerto RDP (3389) abierto a 0.0.0.0/0 | Network |
| 5 | Security | `db-open-sg` | Puerto MSSQL (1433) abierto a 0.0.0.0/0 | Network |
| 6 | Security | `iam-user-no-mfa` | Usuario IAM sin MFA habilitado | IAM |
| 7 | Security | `iam-user-dev-admin` | AdministratorAccess adjunto directamente al usuario | IAM |

### 🟠 HIGH (10 hallazgos)

| # | Dominio | Recurso | Hallazgo | Stack |
|---|---|---|---|---|
| 1 | Security | `rds-public-mysql` | RDS con `PubliclyAccessible = True` | Database |
| 2 | Security | `rds-public-mysql` | RDS sin Multi-AZ en entorno production | Database |
| 3 | Security | `iam-user-svc-integration` | Access key sin rotación +90 días | IAM |
| 4 | Security | `iam-user-ex-employee` | Usuario IAM inactivo 90+ días | IAM |
| 5 | Security | `iam-user-emergency` | Política con permisos `*:*` adjunta al usuario | IAM |
| 6 | FinOps | `ec2-oversized-backend` | EC2 t3.micro con CPU promedio ~2% en 7 días | Compute |
| 7 | FinOps | `rds-public-mysql` | RDS con CPU < 10% en 7 días | Database |
| 8 | FinOps | `rds-stopped-postgres` | RDS detenida por más de 7 días | Database |
| 9 | FinOps | `alb-idle-demo` | ALB sin tráfico en los últimos 7 días | Network |
| 10 | FinOps | `cf-webapp-principal` | CloudFront sin WAF asociado | Frontend |

### 🟡 MEDIUM (17 hallazgos)

| # | Dominio | Recurso | Hallazgo | Stack |
|---|---|---|---|---|
| 1 | Security | VPC `10.0.0.0/16` | VPC sin Flow Logs activos | Network |
| 2 | Security | `bucket-public-demo` | S3 bucket sin server access logging | Storage |
| 3 | Security | `bucket-applogs-demo` | S3 bucket sin server access logging | Storage |
| 4 | Security | `fn-unused-processor` | Lambda sin log group con retención configurada | Compute |
| 5 | Security | `cf-admin-panel` | CloudFront sin WAF asociado | Frontend |
| 6 | FinOps | `ec2-stopped-staging` | EC2 en estado stopped por más de 7 días | Compute |
| 7 | FinOps | `vol-orphan-data` | Volumen EBS de 8 GB sin adjuntar por más de 7 días | Storage |
| 8 | FinOps | `bucket-public-demo` | S3 bucket sin lifecycle policy | Storage |
| 9 | FinOps | `bucket-applogs-demo` | S3 bucket sin lifecycle policy | Storage |
| 10 | Compliance | `ec2-no-tags` | EC2 sin tag `Owner` | Compute |
| 11 | Compliance | `ec2-no-tags` | EC2 sin tag `Project` | Compute |
| 12 | Compliance | `ec2-no-tags` | EC2 sin tag `Environment` | Compute |
| 13 | Compliance | `ec2-no-tags` | EC2 sin tag `CostCenter` | Compute |
| 14 | Compliance | `bucket-public-demo` | S3 sin tags `Owner`, `Project`, `Environment`, `CostCenter` | Storage |
| 15 | Compliance | `bucket-applogs-demo` | S3 sin tag `CostCenter` | Storage |
| 16 | Compliance | `rds-public-mysql` | RDS sin tag `CostCenter` | Database |
| 17 | Compliance | `tbl-inactive-sessions` | DynamoDB sin tags `Owner`, `Project`, `Environment` | Database |

### 🔵 LOW (6 hallazgos)

| # | Dominio | Recurso | Hallazgo | Stack |
|---|---|---|---|---|
| 1 | FinOps | `eip-orphan-demo` | Elastic IP no asociada a ningún recurso | Network |
| 2 | FinOps | `fn-unused-processor` | Lambda sin invocaciones en 30+ días | Compute |
| 3 | FinOps | `fn-legacy-webhook` | Lambda sin invocaciones en 30+ días | Compute |
| 4 | FinOps | `tbl-inactive-sessions` | DynamoDB con < 10 ops/día en 7 días | Database |
| 5 | FinOps | `bucket-archive-demo` | S3 sin lifecycle hacia Glacier (datos en Standard) | Storage |
| 6 | Compliance | `fn-legacy-webhook` | Lambda sin tag `CostCenter` | Compute |

---

## Resumen de Hallazgos Esperados

| Severidad | Cantidad | Dominio Principal |
|---|---|---|
| 🔴 Critical | 7 | Security (IAM, Network) |
| 🟠 High | 10 | Security + FinOps |
| 🟡 Medium | 17 | Security + FinOps + Compliance |
| 🔵 Low | 6 | FinOps + Compliance |
| **Total** | **40** | |

### Ahorro Potencial Estimado (mensual)

> **Nota:** esta infraestructura de muestra usa recursos **free-tier-friendly**
> (EC2 t3.micro, RDS db.t3.micro, EBS 8 GB, sin NAT Gateway) para minimizar el
> consumo de créditos AWS. Por eso los montos de ahorro son menores que en un
> escenario de producción real. El agente detecta los mismos **tipos** de
> hallazgos independientemente del tamaño del recurso.

Valores reales de la ejecución del CGA sobre esta muestra:

| Recurso | Tipo | Ahorro estimado USD/mes |
|---|---|---|
| `ec2-oversized-backend` (t3.micro subutilizada) | Rightsizing | ~$4.55 |
| `ec2-no-tags` (t3.micro subutilizada) | Rightsizing | ~$4.55 |
| `alb-idle-demo` (eliminar) | Eliminación | ~$18.40 |
| `tbl-inactive-sessions` (DynamoDB → on-demand) | Rightsizing | ~$3.98 |
| `tbl-inactive-sessions` (tabla inactiva) | Eliminación | ~$4.55 |
| `eip-orphan-demo` (liberar) | Eliminación | ~$3.65 |
| `vol-orphan-data` 8 GB gp3 (eliminar) | Eliminación | ~$0.64 |
| **Total potencial detectado** | | **~$39.68/mes** |

> En un despliegue de producción con instancias reales (t3.large, db.t3.medium,
> NAT Gateways, volúmenes grandes), el ahorro potencial detectado sería del orden
> de **$150-200/mes** o más.

---

## Notas de Implementación

**¿Por qué las instancias EC2 no muestran CPU baja inmediatamente?**
Las instancias recién creadas tendrán CPU en 0% (detenidas) o valores iniciales. El CGA usa métricas de CloudWatch de los últimos 7 días. Para una demo realista, espera 24 horas o usa el checker de instancias detenidas que no requiere historial de métricas.

**¿La RDS stopped requiere acción manual?**
Sí. CloudFormation crea las instancias RDS en estado `available`. Para simular el hallazgo "detenida +7 días", ejecuta:
```bash
aws rds stop-db-instance --db-instance-identifier <rds-stopped-postgres-id>
```
El CGA detectará el estado `stopped` en la próxima ejecución.

**¿Los usuarios IAM inactivos se detectan de inmediato?**
Los usuarios recién creados no tienen historial de uso. El hallazgo "inactivo 90+ días" se basa en el Credential Report de IAM. En cuentas nuevas, los usuarios sin `PasswordLastUsed` ni `AccessKeyLastUsed` se reportan como inactivos.
