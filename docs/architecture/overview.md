# Arquitectura General — Cloud Governance Agent (CGA)

## Versión: 1.0.0 | Fecha: 2026-09-07 | Autor: Marcelo Dev

---

## 1. Visión General

El CGA es una solución **serverless** desplegada completamente en AWS que opera como un agente de auditoría continua. No requiere servidores permanentes ni agentes instalados en los recursos auditados — se apoya exclusivamente en las APIs de AWS para recolectar información, analizar el estado de los recursos y distribuir los resultados.

La arquitectura sigue el patrón **Event-Driven + Modular Checkers**, donde cada dominio de auditoría (Seguridad, FinOps, Cumplimiento) es independiente y puede extenderse sin afectar los demás.

---

## 2. Diagrama de Componentes AWS

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CUENTA AWS — us-east-1                                                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  CAPA DE TRIGGERS                                                │    │
│  │                                                                  │    │
│  │  ┌──────────────────────────┐  ┌──────────────────────────────┐ │    │
│  │  │  Amazon EventBridge      │  │  Invocación Manual           │ │    │
│  │  │  Scheduler               │  │  AWS CLI / Consola / Kiro    │ │    │
│  │  │  cron(0 8 ? * MON *)     │  │                              │ │    │
│  │  └────────────┬─────────────┘  └──────────────┬───────────────┘ │    │
│  └───────────────┼──────────────────────────────┼──────────────────┘    │
│                  └──────────────┬───────────────┘                       │
│                                 ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  CAPA DE CÓMPUTO                                                  │   │
│  │                                                                   │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │  AWS Lambda — CGA Orchestrator                              │  │   │
│  │  │  Python 3.12 | 512 MB RAM | Timeout: 900s                  │  │   │
│  │  │                                                             │  │   │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────┐ │  │   │
│  │  │  │  Security   │ │   FinOps    │ │    Compliance        │ │  │   │
│  │  │  │  Checkers   │ │  Checkers  │ │    Checkers          │ │  │   │
│  │  │  │             │ │            │ │                      │ │  │   │
│  │  │  │ • IAM       │ │ • EC2      │ │ • Tagging            │ │  │   │
│  │  │  │ • S3        │ │ • RDS      │ │   (Owner, Project,   │ │  │   │
│  │  │  │ • Network   │ │ • Lambda   │ │    Environment,      │ │  │   │
│  │  │  │ • RDS       │ │ • Storage  │ │    CostCenter)       │ │  │   │
│  │  │  │ • CloudFront│ │ • Network  │ │                      │ │  │   │
│  │  │  │ • Logging   │ │ • DynamoDB │ │                      │ │  │   │
│  │  │  └──────┬──────┘ └─────┬──────┘ └──────────┬───────────┘ │  │   │
│  │  │         └──────────────┼─────────────────── ┘             │  │   │
│  │  │                        ▼                                   │  │   │
│  │  │              ┌──────────────────┐                          │  │   │
│  │  │              │   Aggregator     │                          │  │   │
│  │  │              │ Consolida,       │                          │  │   │
│  │  │              │ deduplica y      │                          │  │   │
│  │  │              │ ordena findings  │                          │  │   │
│  │  │              └────────┬─────────┘                          │  │   │
│  │  │                       ▼                                    │  │   │
│  │  │              ┌──────────────────┐                          │  │   │
│  │  │              │ Report Generator │                          │  │   │
│  │  │              │ HTML + JSON      │                          │  │   │
│  │  │              └────────┬─────────┘                          │  │   │
│  │  │                       ▼                                    │  │   │
│  │  │              ┌──────────────────┐                          │  │   │
│  │  │              │    Notifier      │                          │  │   │
│  │  │              │ Enruta por rol   │                          │  │   │
│  │  │              └────────┬─────────┘                          │  │   │
│  │  └───────────────────────┼────────────────────────────────────┘  │   │
│  └──────────────────────────┼─────────────────────────────────────── ┘  │
│                             │                                            │
│       ┌─────────────────────┼──────────────────────┐                    │
│       ▼                     ▼                      ▼                    │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────────┐       │
│  │  Amazon S3   │  │  Amazon SES    │  │  Amazon CloudWatch     │       │
│  │              │  │                │  │                        │       │
│  │  cga-reports │  │ → Auditoría    │  │  Logs (JSON)           │       │
│  │  /{año}/     │  │ → FinOps       │  │  Métricas              │       │
│  │  {mes}/      │  │ → Seguridad    │  │  Alarmas               │       │
│  │  {día}/      │  │ → Owner        │  │                        │       │
│  │  report.json │  │                │  │                        │       │
│  └──────────────┘  └────────────────┘  └────────────────────────┘       │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  APIS AWS CONSULTADAS (solo lectura + s3:PutObject + ses:Send*)   │  │
│  │  EC2 · RDS · S3 · IAM · Lambda · CloudFront · ECS · DynamoDB     │  │
│  │  VPC · CloudTrail · CloudWatch · Cost Explorer · ELB              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Descripción de Componentes

### 3.1 Triggers

| Componente | Tipo | Descripción |
|---|---|---|
| EventBridge Scheduler | Programado | Dispara la Lambda cada lunes a las 08:00 AM UTC con payload `{"execution_type": "scheduled"}` |
| Invocación Manual | On-demand | Invocación directa via CLI, consola AWS o Kiro con payload `{"execution_type": "on-demand"}` |

### 3.2 Lambda Orchestrator

Núcleo del agente. Coordina la ejecución paralela de los checkers usando `ThreadPoolExecutor` con 3 workers (uno por dominio). Gestiona el ciclo completo: auditoría → agregación → reporte → notificación.

**Configuración:**
- Runtime: Python 3.12
- Memoria: 512 MB
- Timeout: 900 segundos (15 minutos)
- Log Group: `/aws/lambda/cloud-governance-agent`

### 3.3 Checkers (14 módulos)

Cada checker es un módulo Python independiente que implementa `BaseChecker`. Se conecta a las APIs de AWS correspondientes, extrae el estado de los recursos y genera objetos `Finding` con severidad, descripción y recomendación.

**Checkers de Seguridad (6):** `iam_checker`, `s3_checker`, `network_checker`, `rds_checker`, `cloudfront_checker`, `logging_checker`

**Checkers de FinOps (6):** `ec2_checker`, `rds_checker`, `lambda_checker`, `storage_checker`, `network_checker`, `dynamodb_checker`

**Checkers de Cumplimiento (1):** `tagging_checker`

### 3.4 Aggregator

Recibe la lista consolidada de `Finding` de los tres dominios. Realiza deduplicación por `resource_id + category`, ordena por severidad y construye el `ReportSummary` con totales y ahorro potencial estimado.

### 3.5 Report Generator

Produce dos artefactos:
- **JSON** (`report.json`): Reporte completo con evidencias, subido a S3
- **HTML** (`report.html`): Reporte visual con resumen ejecutivo, tablas por dominio y top oportunidades de ahorro, con estilos inline para compatibilidad con clientes de email

### 3.6 Notifier

Enruta los hallazgos al destinatario correcto según el rol usando `ses:send_raw_email` con adjunto HTML (MIME multipart).

### 3.7 Amazon S3 — Bucket de Reportes

Almacena todos los reportes JSON con la estructura:
```
s3://cga-reports-{account-id}/
  └── 2026/
      └── 09/
          └── 07/
              └── report-{uuid}.json
```
Lifecycle policy: retención 365 días. Cifrado: SSE-S3.

### 3.8 Amazon SES

Servicio de envío de emails. Envía el reporte HTML como adjunto a los destinatarios segmentados por rol. Requiere que los emails estén verificados en SES (o estar fuera de sandbox para producción).

### 3.9 Amazon CloudWatch

- **Logs**: todos los logs de la Lambda en formato JSON estructurado, retención 90 días
- **Métricas**: `CGA/TotalFindings`, `CGA/PotentialSavingUSD`, `CGA/ExecutionDurationSeconds`
- **Alarma**: `CGA-Lambda-Errors` — notifica al SNS Topic si hay 1+ errores en 5 minutos

---

## 4. Seguridad de la Arquitectura

### Principio de mínimo privilegio
El rol IAM de la Lambda tiene únicamente los permisos de **lectura** sobre los servicios auditados, más `s3:PutObject` para guardar reportes y `ses:SendRawEmail` para notificaciones.

### Sin credenciales en código
Toda la configuración sensible (emails, umbrales) se pasa como variables de entorno desde CDK. No hay secrets hardcodeados.

### Cifrado en reposo
Los reportes en S3 se cifran con SSE-S3 por defecto.

### Trazabilidad completa
Cada ejecución genera logs JSON estructurados en CloudWatch con `report_id`, `execution_type`, `duration_ms` y resumen de hallazgos.

---

## 5. Consideraciones de Escalabilidad

| Escenario | Comportamiento |
|---|---|
| Cuenta con +500 recursos | Dentro del timeout de 15 min; los checkers corren en paralelo |
| Multi-región | Extender `aws_client.py` para iterar sobre regiones configuradas |
| Multi-cuenta | Usar STS AssumeRole para auditar cuentas adicionales (roadmap v2) |
| Nuevos servicios | Agregar un nuevo checker sin modificar el orquestador |
