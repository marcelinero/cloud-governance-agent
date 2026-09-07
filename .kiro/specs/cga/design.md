# Diseño — Cloud Governance Agent (CGA)

## 1. Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRIGGERS                                  │
│  ┌─────────────────────┐      ┌──────────────────────────────┐  │
│  │  EventBridge        │      │  Invocación Manual           │  │
│  │  (Lunes 08:00 AM)   │      │  (CLI / Consola / Kiro)      │  │
│  └──────────┬──────────┘      └──────────────┬───────────────┘  │
└─────────────┼───────────────────────────────┼───────────────────┘
              │                               │
              └──────────────┬────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LAMBDA — CGA Orchestrator                      │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Security    │  │  FinOps      │  │  Compliance          │  │
│  │  Checker     │  │  Checker     │  │  Checker             │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         └─────────────────┼──────────────────────┘              │
│                           ▼                                      │
│                  ┌────────────────┐                              │
│                  │  Finding       │                              │
│                  │  Aggregator    │                              │
│                  └────────┬───────┘                              │
│                           ▼                                      │
│                  ┌────────────────┐                              │
│                  │  Report        │                              │
│                  │  Generator     │                              │
│                  └────────┬───────┘                              │
│                           ▼                                      │
│                  ┌────────────────┐                              │
│                  │  Notifier      │                              │
│                  └────────┬───────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  S3 Bucket  │  │  Amazon SES │  │  CloudWatch │
   │  (Reports)  │  │  (Emails)   │  │  (Logs)     │
   └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 2. Estructura del Proyecto

```
cloud-governance-agent/
├── infrastructure/                  # AWS CDK
│   ├── app.py                       # Entry point CDK
│   ├── cdk.json
│   ├── requirements.txt
│   └── stacks/
│       └── cga_stack.py             # Stack principal
│
├── src/                             # Código Lambda
│   ├── handler.py                   # Entry point Lambda (orquestador)
│   ├── checkers/
│   │   ├── __init__.py
│   │   ├── security/
│   │   │   ├── __init__.py
│   │   │   ├── iam_checker.py
│   │   │   ├── s3_checker.py
│   │   │   ├── network_checker.py
│   │   │   ├── rds_checker.py
│   │   │   ├── cloudfront_checker.py
│   │   │   └── logging_checker.py
│   │   ├── finops/
│   │   │   ├── __init__.py
│   │   │   ├── ec2_checker.py
│   │   │   ├── rds_checker.py
│   │   │   ├── lambda_checker.py
│   │   │   ├── storage_checker.py
│   │   │   ├── network_checker.py
│   │   │   └── dynamodb_checker.py
│   │   └── compliance/
│   │       ├── __init__.py
│   │       └── tagging_checker.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── aggregator.py            # Consolida hallazgos
│   │   ├── report_generator.py      # Genera HTML y JSON
│   │   ├── notifier.py              # Envía emails via SES
│   │   └── models.py                # Modelos de datos (Finding, Report)
│   └── utils/
│       ├── __init__.py
│       ├── aws_client.py            # Factory de clientes boto3
│       └── logger.py                # Logger estructurado JSON
│
├── tests/
│   ├── unit/
│   │   ├── checkers/
│   │   └── core/
│   └── integration/
│
├── .kiro/
│   └── specs/
│       └── cga/
│           ├── spec.md
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
│
├── README.md
├── .gitignore
└── requirements-dev.txt
```

---

## 3. Modelos de Datos

### Finding (Hallazgo)

```python
@dataclass
class Finding:
    id: str                    # UUID único
    domain: str                # "security" | "finops" | "compliance"
    category: str              # "iam" | "s3" | "ec2" | "rds" | etc.
    severity: str              # "critical" | "high" | "medium" | "low"
    resource_id: str           # ARN o ID del recurso
    resource_type: str         # "AWS::EC2::Instance" etc.
    region: str
    account_id: str
    title: str                 # Título corto del hallazgo
    description: str           # Descripción detallada
    recommendation: str        # Acción recomendada
    owner: str                 # Tag Owner del recurso (si existe)
    project: str               # Tag Project del recurso (si existe)
    cost_center: str           # Tag CostCenter (si existe)
    estimated_monthly_cost: float   # Costo mensual estimado en USD
    potential_saving: float         # Ahorro potencial en USD
    timestamp: str             # ISO 8601
    evidence: dict             # Datos crudos del recurso auditado
```

### Report (Reporte)

```python
@dataclass
class Report:
    report_id: str
    account_id: str
    account_name: str
    region: str
    generated_at: str          # ISO 8601
    execution_type: str        # "scheduled" | "on-demand"
    summary: ReportSummary
    findings: List[Finding]

@dataclass
class ReportSummary:
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    total_estimated_cost: float
    total_potential_saving: float
    findings_by_domain: dict   # {"security": 12, "finops": 8, "compliance": 5}
```

---

## 4. Componentes Principales

### 4.1 Lambda Orchestrator (`handler.py`)

Punto de entrada de la Lambda. Responsabilidades:
1. Inicializar el logger y los clientes AWS
2. Ejecutar en paralelo (ThreadPoolExecutor) los tres checkers principales
3. Pasar los hallazgos al Aggregator
4. Invocar el Report Generator
5. Invocar el Notifier
6. Almacenar el reporte JSON en S3
7. Retornar un resumen de ejecución

### 4.2 Checkers

Cada checker es una clase independiente que implementa la interfaz:

```python
class BaseChecker:
    def run(self) -> List[Finding]:
        """Ejecuta todos los checks del módulo y retorna hallazgos."""
        raise NotImplementedError
```

Principio: un checker por servicio AWS, agrupados por dominio. Cada método interno corresponde a un check específico del requirements.

### 4.3 Aggregator (`aggregator.py`)

Recibe todos los hallazgos de los checkers, los deduplica, los ordena por severidad y los agrupa por:
- Dominio (security, finops, compliance)
- Propietario (tag Owner)
- Centro de costo (tag CostCenter)

### 4.4 Report Generator (`report_generator.py`)

Genera dos artefactos:
- **JSON**: reporte completo con todos los hallazgos y evidencias, guardado en S3
- **HTML**: reporte visual con resumen ejecutivo, tablas de hallazgos por dominio, gráficos de severidad y estimados de ahorro. Adjuntado al email.

La plantilla HTML usa estilos inline para compatibilidad máxima con clientes de email.

### 4.5 Notifier (`notifier.py`)

Enruta las notificaciones según el rol:

| Destinatario | Contenido |
|---|---|
| Auditoría | Reporte completo HTML |
| FinOps | Solo hallazgos de dominio `finops` |
| Riesgos/Seguridad | Solo hallazgos de dominio `security` |
| Owner del recurso | Hallazgos donde `finding.owner == email` |

Usa Amazon SES con `send_raw_email` para adjuntar el HTML como archivo.

---

## 5. Infraestructura CDK (`cga_stack.py`)

### Recursos desplegados:

| Recurso | Descripción |
|---|---|
| `aws_lambda.Function` | Función CGA Orchestrator, Python 3.12, 512MB RAM, timeout 900s |
| `aws_s3.Bucket` | Bucket de reportes con SSE-S3, lifecycle 365 días, versionado |
| `aws_iam.Role` | Rol Lambda con permisos mínimos necesarios |
| `aws_events.Rule` | EventBridge rule: cron lunes 08:00 UTC |
| `aws_logs.LogGroup` | Log group con retención 90 días |
| `aws_cloudwatch.Alarm` | Alarma por errores de la Lambda |
| `aws_sns.Topic` | Topic SNS para alertas de fallo |

### Permisos IAM del rol Lambda (mínimo privilegio):

```
ec2:Describe*
rds:Describe*
s3:GetBucketAcl, GetBucketPolicy, GetBucketLogging,
   GetBucketLifecycleConfiguration, GetBucketPublicAccessBlock,
   ListAllMyBuckets, PutObject
iam:ListUsers, ListAccessKeys, GetLoginProfile,
    ListAttachedUserPolicies, ListMFADevices, GenerateCredentialReport
lambda:ListFunctions, GetFunction
cloudfront:ListDistributions, GetDistribution
cloudtrail:GetTrailStatus, DescribeTrails
cloudwatch:GetMetricStatistics, PutMetricData
logs:CreateLogGroup, CreateLogStream, PutLogEvents
cost-explorer:GetCostAndUsage
ses:SendRawEmail
ecs:ListClusters, ListServices, DescribeServices
dynamodb:ListTables, DescribeTable
ec2:DescribeAddresses, DescribeNatGateways,
    DescribeVolumes, DescribeSnapshots, DescribeImages
elasticloadbalancing:DescribeLoadBalancers,
                     DescribeTargetGroups
```

---

## 6. Configuración (Variables de Entorno)

| Variable | Descripción | Ejemplo |
|---|---|---|
| `REPORTS_BUCKET` | Nombre del bucket S3 de reportes | `cga-reports-<account-id>` |
| `AUDIT_EMAIL` | Email del equipo de auditoría | `audit@empresa.com` |
| `FINOPS_EMAIL` | Email del equipo FinOps | `finops@empresa.com` |
| `SECURITY_EMAIL` | Email del equipo de seguridad | `security@empresa.com` |
| `SES_SENDER_EMAIL` | Email remitente verificado en SES | `cga-noreply@empresa.com` |
| `AWS_ACCOUNT_NAME` | Nombre descriptivo de la cuenta | `Producción` |
| `CPU_THRESHOLD_PERCENT` | Umbral de CPU para detectar subutilización | `10` |
| `STOPPED_DAYS_THRESHOLD` | Días detenido para alertar | `7` |
| `KEY_AGE_DAYS_THRESHOLD` | Días sin rotación de access key | `90` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

---

## 7. Flujo de Ejecución

```
1. Trigger (EventBridge o manual)
        │
2. Lambda inicia → logger JSON, carga configuración
        │
3. Ejecuta checkers en paralelo (ThreadPoolExecutor, max 3 workers)
   ├── SecurityChecker.run()   → List[Finding]
   ├── FinOpsChecker.run()     → List[Finding]
   └── ComplianceChecker.run() → List[Finding]
        │
4. Aggregator consolida, deduplica y ordena hallazgos
        │
5. ReportGenerator genera:
   ├── report.json  → upload a S3
   └── report.html  → buffer en memoria
        │
6. Notifier envía emails segmentados por rol via SES
        │
7. Lambda retorna resumen: { total_findings, critical, saving_usd, duration_s }
        │
8. CloudWatch registra métricas y logs
```

---

## 8. Decisiones de Diseño

| Decisión | Alternativa considerada | Razón |
|---|---|---|
| Lambda monolítica con módulos | Step Functions | Menor costo, menor complejidad para MVP; fácil migrar después |
| ThreadPoolExecutor para checkers | asyncio | boto3 no es async nativo; threads es más simple y suficiente |
| HTML inline para email | PDF | SES soporta adjuntos HTML sin dependencias externas de PDF |
| CDK Python | Terraform | Mismo lenguaje que el proyecto, ecosistema AWS nativo |
| SSM Parameter Store para config | Secrets Manager | Los parámetros no son secretos, SSM es suficiente y más barato |
| Un checker por servicio | Un checker por dominio | Facilita testing unitario y extensión independiente |
