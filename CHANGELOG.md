# Changelog — Cloud Governance Agent (CGA)

Todos los cambios notables de este proyecto están documentados en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Pendiente
- Implementación de checkers de seguridad (IAM, S3, Network, RDS, CloudFront, Logging)
- Implementación de checkers de FinOps (EC2, RDS, Lambda, Storage, Network, DynamoDB)
- Implementación de checker de cumplimiento (Tagging)
- Core: Aggregator, ReportGenerator, Notifier, Handler
- Infraestructura CDK
- Tests unitarios con moto
- Soporte multi-región (v2)
- Soporte multi-cuenta via STS AssumeRole (v2)

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

[Unreleased]: https://github.com/tu-usuario/cloud-governance-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tu-usuario/cloud-governance-agent/releases/tag/v0.1.0
