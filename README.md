# Cloud Governance Agent (CGA)

> Agente de auditoría continua, seguridad y optimización de costos para cuentas AWS nativas en la nube.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![AWS CDK v2](https://img.shields.io/badge/AWS%20CDK-v2-orange.svg)](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ¿Qué es el CGA?

El **Cloud Governance Agent** es un agente serverless desplegado en AWS que audita automáticamente los recursos de tu cuenta, identifica riesgos de seguridad, oportunidades de optimización de costos y brechas de cumplimiento, y notifica a los equipos responsables con reportes detallados.

Está diseñado para equipos de **Auditoría TI**, **FinOps**, **Seguridad** e **Ingeniería de Infraestructura** que necesitan visibilidad continua sin depender de procesos manuales.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRIGGERS                                  │
│  ┌─────────────────────┐      ┌──────────────────────────────┐  │
│  │  EventBridge        │      │  Invocación Manual           │  │
│  │  (Lunes 08:00 AM)   │      │  (CLI / Consola / Kiro)      │  │
│  └──────────┬──────────┘      └──────────────┬───────────────┘  │
└─────────────┼───────────────────────────────┼───────────────────┘
              └──────────────┬────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LAMBDA — CGA Orchestrator                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Security    │  │  FinOps      │  │  Compliance          │  │
│  │  Checker     │  │  Checker     │  │  Checker             │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         └─────────────────┼──────────────────────┘              │
│                           ▼                                      │
│                  ┌────────────────┐                              │
│                  │  Aggregator    │                              │
│                  └────────┬───────┘                              │
│                           ▼                                      │
│                  ┌────────────────┐                              │
│                  │ Report Generator│                             │
│                  └────────┬───────┘                              │
│                           ▼                                      │
│                  ┌────────────────┐                              │
│                  │   Notifier     │                              │
│                  └────────┬───────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  S3 Bucket  │  │ Amazon SES  │  │  CloudWatch │
   │  (Reports)  │  │  (Emails)   │  │  (Logs)     │
   └─────────────┘  └─────────────┘  └─────────────┘
```

Para diagramas detallados ver [`docs/architecture/`](docs/architecture/).

---

## Dominios de Auditoría

### 🔐 Seguridad y Cumplimiento
| Check | Severidad |
|---|---|
| Usuarios IAM sin MFA | Critical |
| Access keys sin rotación +90 días | High |
| Security Groups con puertos críticos abiertos (22, 3389, 3306…) | Critical |
| Buckets S3 con acceso público | Critical |
| Distribuciones CloudFront sin WAF | High |
| Instancias RDS con acceso público | High |
| VPCs sin Flow Logs | Medium |
| CloudTrail deshabilitado | Critical |
| Usuarios IAM inactivos +90 días | Medium |

### 💰 Optimización de Costos (FinOps)
| Check | Severidad |
|---|---|
| EC2 con CPU < 10% en 7 días | High |
| EC2 detenidas +7 días | Medium |
| Elastic IPs no asociadas | Low |
| Volúmenes EBS sin adjuntar +7 días | Medium |
| Snapshots huérfanos +30 días | Low |
| NAT Gateways sin tráfico +7 días | High |
| Load Balancers sin tráfico +7 días | High |
| RDS con CPU < 10% en 7 días | High |
| Lambda sin invocaciones +30 días | Low |
| Tablas DynamoDB sin uso +7 días | Low |

### 🏷️ Cumplimiento de Etiquetado
| Check | Severidad |
|---|---|
| Recursos sin tags obligatorios (Owner, Project, Environment, CostCenter) | Medium |

---

## Notificaciones por Rol

| Destinatario | Contenido recibido |
|---|---|
| **Auditoría** | Reporte completo HTML con todos los hallazgos |
| **FinOps** | Solo hallazgos de costos con ahorro potencial estimado |
| **Seguridad / Riesgos** | Solo hallazgos de seguridad priorizados por severidad |
| **Owner del recurso** | Hallazgos específicos de sus recursos (via tag `Owner`) |

---

## Estructura del Proyecto

```
cloud-governance-agent/
├── docs/                            # Documentación del proyecto
│   ├── architecture/                # Descripción de arquitectura
│   ├── adr/                         # Architecture Decision Records
│   └── diagrams/                    # Diagramas Mermaid (.md)
├── infrastructure/                  # AWS CDK (Python)
│   ├── app.py
│   ├── cdk.json
│   └── stacks/
│       └── cga_stack.py
├── src/                             # Código fuente Lambda
│   ├── handler.py                   # Orquestador principal
│   ├── checkers/
│   │   ├── security/                # Checkers de seguridad
│   │   ├── finops/                  # Checkers de costos
│   │   └── compliance/              # Checkers de cumplimiento
│   ├── core/
│   │   ├── aggregator.py
│   │   ├── report_generator.py
│   │   ├── notifier.py
│   │   └── models.py
│   └── utils/
│       ├── aws_client.py
│       └── logger.py
├── tests/
│   ├── unit/
│   └── integration/
├── .kiro/specs/cga/                 # Especificación del proyecto
│   ├── spec.md
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── .gitignore
└── requirements-dev.txt
```

---

## Prerrequisitos

- Python 3.12+
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configurado con credenciales válidas
- [AWS CDK v2](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html): `npm install -g aws-cdk`
- [Node.js 18+](https://nodejs.org/) (requerido por CDK)
- Cuenta AWS con Amazon SES configurado (emails de destino verificados)

---

## Instalación y Despliegue

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/cloud-governance-agent.git
cd cloud-governance-agent
```

### 2. Crear y activar entorno virtual

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. Instalar dependencias de desarrollo

```bash
pip install -r requirements-dev.txt
```

### 4. Configurar parámetros en CDK context

Edita `infrastructure/cdk.json` con tus valores:

```json
{
  "app": "python app.py",
  "context": {
    "account": "748861776779",
    "region": "us-east-1",
    "audit_email": "audit@tuempresa.com",
    "finops_email": "finops@tuempresa.com",
    "security_email": "security@tuempresa.com",
    "ses_sender_email": "cga-noreply@tuempresa.com",
    "account_name": "Mi Cuenta AWS",
    "cpu_threshold_percent": "10",
    "stopped_days_threshold": "7",
    "key_age_days_threshold": "90"
  }
}
```

### 5. Bootstrap CDK (solo la primera vez)

```bash
cd infrastructure
cdk bootstrap aws://748861776779/us-east-1
```

### 6. Desplegar

```bash
cdk deploy
```

---

## Ejecución

### Bajo demanda — AWS CLI

```bash
aws lambda invoke \
  --function-name cloud-governance-agent \
  --payload '{"execution_type": "on-demand"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```

### Bajo demanda — Kiro

Puedes pedirle a Kiro directamente:
> "Ejecuta el Cloud Governance Agent en mi cuenta AWS"

### Programada

Se ejecuta automáticamente todos los **lunes a las 08:00 AM UTC** via EventBridge Scheduler.

---

## Ejemplo de Reporte

```json
{
  "report_id": "cga-2026-09-07-001",
  "account_id": "748861776779",
  "account_name": "Mi Cuenta AWS",
  "generated_at": "2026-09-07T08:05:32Z",
  "execution_type": "scheduled",
  "summary": {
    "total_findings": 24,
    "critical": 3,
    "high": 8,
    "medium": 9,
    "low": 4,
    "total_estimated_cost": 1840.50,
    "total_potential_saving": 612.30,
    "findings_by_domain": {
      "security": 11,
      "finops": 9,
      "compliance": 4
    }
  }
}
```

---

## Tecnologías Utilizadas

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| IaC | AWS CDK v2 (Python) |
| Cómputo | AWS Lambda |
| Scheduler | Amazon EventBridge |
| Reportes | Amazon S3 |
| Notificaciones | Amazon SES |
| Métricas de costos | AWS Cost Explorer |
| Auditoría de recursos | boto3 (EC2, IAM, RDS, S3, CloudFront, ECS, DynamoDB…) |
| Observabilidad | Amazon CloudWatch |
| Tests | pytest + moto |

---

## Documentación

| Documento | Descripción |
|---|---|
| [Requisitos](./kiro/specs/cga/requirements.md) | Requisitos funcionales y no funcionales |
| [Diseño](./kiro/specs/cga/design.md) | Arquitectura, modelos y decisiones técnicas |
| [Tareas](./kiro/specs/cga/tasks.md) | Plan de implementación en 8 fases |
| [ADR-001](docs/adr/ADR-001-serverless-architecture.md) | Decisión: Arquitectura serverless con Lambda |
| [ADR-002](docs/adr/ADR-002-cdk-python.md) | Decisión: CDK Python sobre Terraform |
| [ADR-003](docs/adr/ADR-003-modular-checkers.md) | Decisión: Checkers modulares por servicio |
| [Arquitectura General](docs/architecture/overview.md) | Descripción detallada de componentes |
| [Diagrama de Flujo](docs/diagrams/execution-flow.md) | Flujo de ejecución del agente |
| [Modelo de Datos](docs/diagrams/data-model.md) | Estructura de datos de hallazgos y reportes |
| [CHANGELOG](CHANGELOG.md) | Historial de versiones |
| [CONTRIBUTING](CONTRIBUTING.md) | Guía de contribución |

---

## Contribución

Las contribuciones son bienvenidas. Lee [CONTRIBUTING.md](CONTRIBUTING.md) para el proceso de pull requests y estándares de código.

---

## Licencia

MIT © 2026 — Marcelo Dev

---

## Autor

Desarrollado por un Ingeniero y Auditor de TI con 15 años de experiencia, combinando las mejores prácticas de auditoría con la potencia de los agentes de IA en AWS.
