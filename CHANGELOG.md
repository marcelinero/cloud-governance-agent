# Changelog — Cloud Governance Agent (CGA)

Todos los cambios notables de este proyecto están documentados en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Removed
- `S3SecurityChecker`: se eliminó el check de "bucket sin cifrado en reposo". Desde el
  5-ene-2023 AWS aplica SSE-S3 (AES-256) por defecto a todos los buckets, por lo que la
  ausencia de cifrado dejó de ser un estado posible y el check nunca disparaba. No se
  reemplaza por un check de SSE-S3 vs SSE-KMS porque esa decisión depende de la
  clasificación de datos y las políticas de cada cliente/ambiente, y no aplica como
  regla general.
  ([Default encryption FAQ](https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-encryption-faq.html))
- `S3SecurityChecker`: la recomendación de Block Public Access ahora menciona que AWS
  activa BPA y deshabilita ACLs por defecto en buckets nuevos desde abr-2023, y sugiere
  Object Ownership = `Bucket owner enforced`.
- `IAMChecker`: recomendaciones de MFA y access keys modernizadas para sugerir
  IAM Identity Center (acceso humano) y credenciales temporales (roles, IAM Roles Anywhere).

### Notas
- Ajustes validados contra la documentación oficial de AWS mediante el servidor MCP de AWS.

### Roadmap
- Soporte multi-región (auditar todas las regiones habilitadas)
- Soporte multi-cuenta via STS AssumeRole
- Integración con AWS Security Hub y AWS Config
- Análisis de tendencias históricas de hallazgos entre ejecuciones
- Notificaciones adicionales: Slack, Microsoft Teams, PagerDuty

---

## [1.0.0] — 2026-09-07

Primera versión funcional del Cloud Governance Agent, desplegada y validada
end-to-end en una cuenta AWS real.

### Added

**Checkers de Seguridad (6 módulos, 15 checks)**
- `IAMChecker`: MFA ausente, access keys sin rotar +90d, usuarios inactivos, políticas `*:*` y AdministratorAccess directos
- `S3SecurityChecker`: buckets públicos, sin server access logging (con fault isolation por check)
- `NetworkChecker`: Security Groups con puertos críticos abiertos a 0.0.0.0/0, VPCs sin Flow Logs
- `RDSSecurityChecker`: instancias con acceso público, sin Multi-AZ en producción
- `CloudFrontChecker`: distribuciones sin WAF, HTTP permitido (allow-all)
- `LoggingChecker`: CloudTrail deshabilitado, Lambda sin log group/retención

**Checkers de FinOps (6 módulos, 14 checks)**
- `EC2FinOpsChecker`: CPU baja, instancias detenidas, costo EBS
- `StorageChecker`: S3 sin lifecycle, EBS huérfano, snapshots huérfanos, AMIs sin uso
- `RDSFinOpsChecker`: CPU baja, instancias detenidas (con aviso auto-restart AWS)
- `LambdaFinOpsChecker`: funciones sin invocaciones, Provisioned Concurrency sin uso
- `NetworkFinOpsChecker`: Elastic IPs huérfanas, NAT Gateways/Load Balancers sin tráfico
- `DynamoDBChecker`: tablas inactivas, capacidad PROVISIONED sobredimensionada

**Checker de Cumplimiento**
- `TaggingChecker`: tags obligatorios (Owner, Project, Environment, CostCenter) en EC2, RDS, S3, Lambda, DynamoDB, CloudFront

**Core del agente**
- `Aggregator`: deduplicación, ordenamiento por severidad, resumen ejecutivo
- `ReportGenerator`: reporte JSON (a S3) + HTML con estilos inline
- `Notifier`: routing por rol via Amazon SES (auditoría, FinOps, seguridad, owner)
- `handler.py`: orquestador Lambda con ejecución paralela (ThreadPoolExecutor) y métricas CloudWatch

**Infraestructura (CDK Python)**
- Stack del agente: Lambda 3.12, S3 con lifecycle 365d, rol IAM de mínimo privilegio, EventBridge (lunes 08:00 UTC), alarma CloudWatch, SNS topic
- Infraestructura de muestra (ACME Corp): 6 stacks con 40+ hallazgos intencionales para demostración

**Tests**
- Suite de 30 tests unitarios con `moto` (29 pasan, 1 skip documentado por limitación de moto)
- Cobertura de checkers de seguridad, FinOps, compliance y core

**Documentación**
- README, CHANGELOG, CONTRIBUTING, LICENSE (MIT)
- Arquitectura, 3 ADRs, diagramas Mermaid, modelo de datos
- Reporte de ejemplo real en `docs/sample-report/`

### Validado
- Desplegado en cuenta AWS real (us-east-1)
- Ejecución end-to-end: **57 hallazgos** detectados (8 critical, 14 high, 31 medium, 4 low)
- Reporte generado y almacenado en S3, métricas publicadas en CloudWatch

### Notas
- El envío de email por SES requiere verificar el remitente; en modo demo usa placeholders y falla de forma controlada sin afectar el reporte en S3

---

## [0.1.0] — 2026-09-07

### Added
- Estructura inicial del proyecto
- Especificación completa: requisitos, diseño y plan de tareas (`.kiro/specs/cga/`)
- Documentación base:
  - `README.md` con arquitectura, tabla de checks, instrucciones de despliegue
  - `docs/architecture/overview.md` — descripción detallada de componentes AWS
  - `docs/diagrams/execution-flow.md` — diagramas Mermaid del flujo de ejecución
  - `docs/diagrams/data-model.md` — modelo de datos con diagrama de clases y JSON de ejemplo
  - `docs/adr/ADR-001-serverless-architecture.md` — decisión de arquitectura serverless
  - `docs/adr/ADR-002-cdk-python.md` — decisión de usar CDK Python
  - `docs/adr/ADR-003-modular-checkers.md` — decisión de checkers modulares por servicio
  - `CHANGELOG.md` — este archivo
  - `CONTRIBUTING.md` — guía de contribución
- Estructura de carpetas: `src/`, `infrastructure/`, `tests/`, `docs/`

---

## Guía de Versionado

| Tipo de cambio | Incremento |
|---|---|
| Nuevo checker o feature | MINOR (0.X.0) |
| Corrección de bug | PATCH (0.0.X) |
| Cambio de arquitectura o breaking change | MAJOR (X.0.0) |

## Categorías de Cambios

- **Added**: nuevas funcionalidades
- **Changed**: cambios en funcionalidades existentes
- **Deprecated**: funcionalidades que serán eliminadas en versiones futuras
- **Removed**: funcionalidades eliminadas
- **Fixed**: corrección de bugs
- **Security**: corrección de vulnerabilidades

[Unreleased]: https://github.com/marcelinero/cloud-governance-agent/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/marcelinero/cloud-governance-agent/releases/tag/v1.0.0
[0.1.0]: https://github.com/marcelinero/cloud-governance-agent/releases/tag/v0.1.0
