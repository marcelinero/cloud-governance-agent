# Tareas de Implementación — Cloud Governance Agent (CGA)

## Fase 0: Documentación Base ✅ COMPLETADA

> La documentación se crea desde el inicio del proyecto para garantizar trazabilidad completa.
> Todos los documentos de esta fase ya están creados.

- [x] **TASK-00a** — Crear estructura de carpetas de documentación
  - `docs/architecture/` — descripciones de componentes
  - `docs/adr/` — Architecture Decision Records
  - `docs/diagrams/` — diagramas Mermaid

- [x] **TASK-00b** — Crear `README.md` principal
  - Badges de versión, CDK y licencia
  - Arquitectura ASCII
  - Tabla de checks por dominio (Seguridad, FinOps, Cumplimiento)
  - Instrucciones de despliegue paso a paso
  - Ejemplo de reporte JSON
  - Tabla de documentación con enlaces

- [x] **TASK-00c** — Crear documentación de arquitectura
  - `docs/architecture/overview.md` — diagrama de componentes AWS, descripción de cada componente, consideraciones de seguridad y escalabilidad

- [x] **TASK-00d** — Crear diagramas Mermaid
  - `docs/diagrams/execution-flow.md` — flujo completo de ejecución, manejo de errores, enrutamiento de notificaciones
  - `docs/diagrams/data-model.md` — diagrama de clases, JSON de ejemplo, reglas de negocio del modelo

- [x] **TASK-00e** — Crear Architecture Decision Records (ADR)
  - `docs/adr/ADR-001-serverless-architecture.md` — Lambda vs EC2 vs Fargate vs Step Functions
  - `docs/adr/ADR-002-cdk-python.md` — CDK Python vs CloudFormation vs Terraform vs SAM
  - `docs/adr/ADR-003-modular-checkers.md` — un checker por servicio vs otras alternativas

- [x] **TASK-00f** — Crear `CHANGELOG.md`
  - Formato Keep a Changelog + Semantic Versioning
  - Versión 0.1.0 con documentación base
  - Sección Unreleased con pendientes

- [x] **TASK-00g** — Crear `CONTRIBUTING.md`
  - Setup del entorno de desarrollo
  - Estándares de código (PEP8, black, flake8)
  - Guía paso a paso para agregar un nuevo checker
  - Estándar de tests con moto
  - Proceso de Pull Requests y Conventional Commits

---

## Fase 1: Fundamentos del Proyecto

- [ ] **TASK-01** — Inicializar el proyecto CDK
  - Ejecutar `cdk init app --language python` en `/infrastructure`
  - Configurar `cdk.json` con context: account, region, umbrales
  - Crear `requirements.txt` con dependencias CDK: `aws-cdk-lib`, `constructs`
  - Crear `requirements-dev.txt` con: `pytest`, `boto3`, `moto`, `black`, `flake8`

- [ ] **TASK-02** — Crear el modelo de datos central
  - Implementar `src/core/models.py` con dataclasses `Finding`, `ReportSummary`, `Report`
  - Definir los literales de severidad: `critical`, `high`, `medium`, `low`
  - Definir los literales de dominio: `security`, `finops`, `compliance`

- [ ] **TASK-03** — Implementar utilidades base
  - Implementar `src/utils/logger.py` con logger JSON estructurado usando `logging`
  - Implementar `src/utils/aws_client.py` como factory de clientes boto3 con retry config

---

## Fase 2: Checkers de Seguridad

- [ ] **TASK-04** — Implementar `BaseChecker`
  - Crear `src/checkers/__init__.py` con clase abstracta `BaseChecker`
  - Definir interfaz `run() -> List[Finding]`
  - Implementar método helper `_build_finding()` con generación de UUID

- [ ] **TASK-05** — Implementar `IAMChecker`
  - Archivo: `src/checkers/security/iam_checker.py`
  - Check: usuarios sin MFA habilitado
  - Check: access keys con más de 90 días (configurable por env var)
  - Check: usuarios sin actividad en 90+ días (usar credential report)
  - Check: políticas con `*:*` adjuntas directamente a usuarios

- [ ] **TASK-06** — Implementar `S3SecurityChecker`
  - Archivo: `src/checkers/security/s3_checker.py`
  - Check: buckets con acceso público habilitado (`GetBucketPublicAccessBlock`)
  - Check: buckets sin server access logging
  - Check: buckets sin etiquetas obligatorias (Owner, Project, Environment, CostCenter)

- [ ] **TASK-07** — Implementar `NetworkChecker`
  - Archivo: `src/checkers/security/network_checker.py`
  - Check: Security Groups con puertos críticos abiertos a 0.0.0.0/0 (22, 3389, 3306, 5432, 1433, 27017)
  - Check: Elastic IPs no asociadas (también cuenta para FinOps)
  - Check: VPCs sin Flow Logs activos

- [ ] **TASK-08** — Implementar `RDSSecurityChecker`
  - Archivo: `src/checkers/security/rds_checker.py`
  - Check: instancias RDS con `PubliclyAccessible = True`
  - Check: instancias RDS sin Multi-AZ en entornos productivos

- [ ] **TASK-09** — Implementar `CloudFrontChecker`
  - Archivo: `src/checkers/security/cloudfront_checker.py`
  - Check: distribuciones sin WAF (WebACL) asociado
  - Check: distribuciones con HTTP permitido (no forzando HTTPS)

- [ ] **TASK-10** — Implementar `LoggingChecker`
  - Archivo: `src/checkers/security/logging_checker.py`
  - Check: CloudTrail deshabilitado o no activo en la región
  - Check: funciones Lambda sin log group en CloudWatch

---

## Fase 3: Checkers de FinOps

- [ ] **TASK-11** — Implementar `EC2FinOpsChecker`
  - Archivo: `src/checkers/finops/ec2_checker.py`
  - Check: instancias con CPU promedio < 10% en últimos 7 días (CloudWatch Metrics)
  - Check: instancias en estado `stopped` por más de 7 días
  - Obtener costo mensual estimado de cada instancia via Cost Explorer

- [ ] **TASK-12** — Implementar `StorageChecker`
  - Archivo: `src/checkers/finops/storage_checker.py`
  - Check: buckets S3 sin lifecycle policy configurada
  - Check: snapshots EBS huérfanos (+30 días sin instancia asociada)
  - Check: AMIs no utilizadas con más de 90 días
  - Check: volúmenes EBS en estado `available` por más de 7 días

- [ ] **TASK-13** — Implementar `RDSFinOpsChecker`
  - Archivo: `src/checkers/finops/rds_checker.py`
  - Check: instancias RDS con CPU < 10% en últimos 7 días
  - Check: instancias RDS en estado `stopped` por más de 7 días
  - Obtener costo mensual estimado via Cost Explorer

- [ ] **TASK-14** — Implementar `LambdaFinOpsChecker`
  - Archivo: `src/checkers/finops/lambda_checker.py`
  - Check: funciones Lambda sin invocaciones en los últimos 30 días
  - Detectar funciones con provisioned concurrency sin uso

- [ ] **TASK-15** — Implementar `NetworkFinOpsChecker`
  - Archivo: `src/checkers/finops/network_checker.py`
  - Check: Elastic IPs no asociadas a ningún recurso
  - Check: NAT Gateways sin tráfico en últimos 7 días (CloudWatch BytesOutToDestination)
  - Check: Load Balancers (ALB/NLB) sin tráfico en últimos 7 días

- [ ] **TASK-16** — Implementar `DynamoDBChecker`
  - Archivo: `src/checkers/finops/dynamodb_checker.py`
  - Check: tablas con menos de 10 operaciones read/write por día en últimos 7 días
  - Detectar tablas en modo `PROVISIONED` con capacidad sobredimensionada

---

## Fase 4: Checker de Cumplimiento

- [ ] **TASK-17** — Implementar `TaggingChecker`
  - Archivo: `src/checkers/compliance/tagging_checker.py`
  - Verificar etiquetas obligatorias (`Owner`, `Project`, `Environment`, `CostCenter`) en:
    EC2, RDS, S3, Lambda, ECS Services, DynamoDB, CloudFront
  - Severidad `medium` por recurso sin tag obligatorio
  - Extraer valor del tag `Owner` para routing de notificaciones

---

## Fase 5: Core — Agregación, Reporte y Notificación

- [ ] **TASK-18** — Implementar `Aggregator`
  - Archivo: `src/core/aggregator.py`
  - Consolidar hallazgos de todos los checkers en una sola lista
  - Deduplicar por `resource_id + category`
  - Ordenar por severidad: critical → high → medium → low
  - Construir `ReportSummary` con totales, ahorro potencial y agrupación por dominio
  - Agrupar hallazgos por `owner` para routing de notificaciones

- [ ] **TASK-19** — Implementar `ReportGenerator`
  - Archivo: `src/core/report_generator.py`
  - Generar `report.json` con estructura completa del `Report`
  - Generar `report.html` con:
    - Resumen ejecutivo (totales, ahorro potencial, fecha)
    - Tabla de hallazgos por dominio con colores por severidad
    - Sección de top 5 oportunidades de ahorro
    - Estilos CSS inline para compatibilidad con clientes de email
  - Subir `report.json` a S3 con path `YYYY/MM/DD/report-{id}.json`
  - Retornar HTML como string en memoria para adjuntar al email

- [ ] **TASK-20** — Implementar `Notifier`
  - Archivo: `src/core/notifier.py`
  - Enviar email a equipo de Auditoría con reporte HTML completo adjunto
  - Enviar email a equipo FinOps con solo hallazgos de dominio `finops`
  - Enviar email a equipo de Seguridad con solo hallazgos de dominio `security`
  - Enviar email al owner de cada recurso (si tag `Owner` es un email válido)
  - Usar `ses:send_raw_email` con adjunto HTML (MIME multipart)

- [ ] **TASK-21** — Implementar `handler.py` (orquestador Lambda)
  - Cargar configuración desde variables de entorno
  - Ejecutar los tres grupos de checkers en paralelo con `ThreadPoolExecutor`
  - Invocar Aggregator → ReportGenerator → Notifier en secuencia
  - Registrar métricas de ejecución en CloudWatch (`PutMetricData`)
  - Retornar resumen JSON con: total_findings, critical, saving_usd, duration_s
  - Manejar excepciones globales y registrar en CloudWatch

---

## Fase 6: Infraestructura CDK

- [ ] **TASK-22** — Implementar `CGAStack` en CDK
  - Archivo: `infrastructure/stacks/cga_stack.py`
  - Crear bucket S3 de reportes con SSE-S3, versionado y lifecycle 365 días
  - Crear rol IAM con permisos mínimos definidos en el diseño
  - Crear función Lambda con Python 3.12, 512MB, timeout 900s
  - Pasar todas las variables de entorno a la Lambda desde CDK context
  - Crear EventBridge Rule con cron `cron(0 8 ? * MON *)` apuntando a la Lambda
  - Crear Log Group con retención 90 días
  - Crear alarma CloudWatch por errores de Lambda (threshold: 1 error en 5 min)
  - Crear SNS Topic para notificaciones de fallo de la Lambda

- [ ] **TASK-23** — Implementar `app.py` CDK entry point
  - Archivo: `infrastructure/app.py`
  - Leer account y region desde `cdk.json` context
  - Instanciar `CGAStack` con parámetros de configuración

---

## Fase 7: Tests

- [ ] **TASK-24** — Tests unitarios de checkers de seguridad
  - Usar `moto` para mockear AWS APIs
  - Tests para: `IAMChecker`, `S3SecurityChecker`, `NetworkChecker`
  - Cubrir casos: recurso conforme, recurso no conforme, recurso sin tags

- [ ] **TASK-25** — Tests unitarios de checkers de FinOps
  - Tests para: `EC2FinOpsChecker`, `StorageChecker`, `RDSFinOpsChecker`
  - Mockear métricas de CloudWatch con datos de CPU simulados

- [ ] **TASK-26** — Tests unitarios de core
  - Tests para `Aggregator`: deduplicación, ordenamiento, totales
  - Tests para `ReportGenerator`: validar estructura JSON, validar HTML no vacío
  - Tests para `Notifier`: validar llamadas a SES con destinatarios correctos

---

## Fase 8: Documentación Final y Publicación

- [ ] **TASK-27** — Actualizar `README.md` con capturas y ejemplos reales
  - Agregar screenshot o HTML de muestra del reporte generado
  - Agregar sección de FAQ con preguntas frecuentes
  - Verificar que todos los enlaces de documentación funcionen
  - Actualizar badges con estado real del proyecto

- [ ] **TASK-28** — Crear `.gitignore` y preparar repositorio
  - Ignorar: `cdk.out/`, `__pycache__/`, `.env`, `*.pyc`, `.venv/`, `node_modules/`
  - Inicializar repositorio git
  - Crear commit inicial con toda la estructura

- [ ] **TASK-29** — Actualizar `CHANGELOG.md` con versión 1.0.0
  - Documentar todos los checkers implementados
  - Documentar la infraestructura CDK
  - Marcar todos los items de Unreleased como parte de v1.0.0

- [ ] **TASK-30** — Crear `LICENSE` (MIT)
  - Agregar archivo LICENSE con licencia MIT
  - Verificar que README referencia correctamente la licencia

- [ ] **TASK-31** — Preparar publicación en GitHub
  - Revisar que no hay credenciales ni datos sensibles en el código
  - Agregar GitHub Actions workflow para lint y tests automáticos (`.github/workflows/ci.yml`)
  - Crear release v1.0.0 en GitHub con notas de release

---

## Orden de Implementación Recomendado

```
TASK-00a..g  (Documentación base — YA COMPLETADA ✅)
     ↓
TASK-01 → TASK-02 → TASK-03    (Fundamentos)
     ↓
TASK-04 → TASK-05..10          (Checkers Seguridad)
     ↓
TASK-11..16                    (Checkers FinOps)
     ↓
TASK-17                        (Checker Cumplimiento)
     ↓
TASK-18 → TASK-19 → TASK-20 → TASK-21   (Core)
     ↓
TASK-22 → TASK-23              (CDK)
     ↓
TASK-24..26                    (Tests)
     ↓
TASK-27..31                    (Documentación final y publicación)
```

**Total: 38 tareas (7 completadas) | Estimado: 3-4 semanas de desarrollo**
