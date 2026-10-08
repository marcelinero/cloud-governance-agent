# Política de Tagging de Recursos AWS

**Versión:** 1.0  
**Fecha:** 2025-07-15  
**Proyecto:** Cloud Governance Agent (CGA)

---

## Objetivo

Establecer lineamientos de etiquetado (tagging) para todos los recursos AWS desplegados en la cuenta productiva, permitiendo el aislamiento lógico entre proyectos, la atribución de costos por proyecto/entorno y el cumplimiento de governance automatizado.

---

## 1. Tags Obligatorios

Los siguientes tags deben estar presentes en **todos** los recursos AWS, sin excepción.

| Tag | Descripción | Ejemplo |
|-----|-------------|---------|
| `Project` | Nombre corto del proyecto al que pertenece el recurso | `CGA`, `MI-APP` |
| `Env` | Entorno de despliegue | `PDN`, `DEV`, `STG`, `QA` |
| `Owner` | Equipo o persona responsable del recurso | `CloudOps`, `equipo-backend` |
| `CostCenter` | Centro de costo para facturación separada | `CGA-PDN`, `MIAPP-DEV` |

### Valores permitidos para `Env`

| Valor | Significado |
|-------|-------------|
| `PDN` | Producción |
| `DEV` | Desarrollo |
| `STG` | Staging / Pre-producción |
| `QA`  | Control de calidad |

---

## 2. Tags Recomendados

Opcionales pero altamente recomendados para trazabilidad y gestión del ciclo de vida.

| Tag | Descripción | Ejemplo |
|-----|-------------|---------|
| `Version` | Versión del release desplegado | `1.0.0`, `2.3.1` |
| `ManagedBy` | Herramienta de IaC utilizada | `CDK`, `Terraform`, `Manual` |
| `CreatedDate` | Fecha de creación del recurso | `2025-07-15` (formato YYYY-MM-DD) |

---

## 3. Reglas de Naming

1. **MAYÚSCULAS** — Los valores de `Project` y `Env` deben ir siempre en mayúsculas.  
   ✓ `CGA` &nbsp;&nbsp; ✗ `cga`

2. **Sin espacios** — Usar guión `-` como separador cuando se necesite combinar palabras.  
   ✓ `MI-APP` &nbsp;&nbsp; ✗ `MI APP`

3. **Longitud máxima** — 256 caracteres por valor de tag (límite AWS).

4. **Claves en PascalCase** — Las claves de los tags son sensibles a mayúsculas en AWS. Usar siempre el formato PascalCase definido en esta política.  
   ✓ `Project`, `Env`, `Owner`, `CostCenter`  
   ✗ `project`, `PROJECT`, `env`, `cost_center`

5. **Consistencia** — El valor de `CostCenter` debe seguir el patrón `{Project}-{Env}` para mantener coherencia con los filtros de Cost Explorer.

---

## 4. Cómo aplicar en CDK (Python)

### Opción A — A nivel de Stack (recomendado)

Aplicar los tags en el constructor del stack para que se propaguen automáticamente a todos los recursos hijos.

```python
from aws_cdk import Stack, Tags
from constructs import Construct

class MiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Tags obligatorios — se propagan a todos los recursos del stack
        Tags.of(self).add("Project", "CGA")
        Tags.of(self).add("Env", "PDN")
        Tags.of(self).add("Owner", "CloudOps")
        Tags.of(self).add("CostCenter", "CGA-PDN")

        # Tags recomendados
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Version", "1.0.0")
        Tags.of(self).add("CreatedDate", "2025-07-15")
```

### Opción B — A nivel de aplicación en `app.py`

Para aplicar los tags a todos los stacks de una aplicación CDK de forma centralizada:

```python
import aws_cdk as cdk
from mi_proyecto.mi_stack import MiStack

app = cdk.App()

stack = MiStack(app, "MiStack")

# Tags obligatorios aplicados a nivel de app
cdk.Tags.of(stack).add("Project", "CGA")
cdk.Tags.of(stack).add("Env", "PDN")
cdk.Tags.of(stack).add("Owner", "CloudOps")
cdk.Tags.of(stack).add("CostCenter", "CGA-PDN")

app.synth()
```

### Opción C — Parámetros dinámicos por entorno

Para gestionar múltiples entornos evitando valores hardcodeados:

```python
import aws_cdk as cdk
from mi_proyecto.mi_stack import MiStack

app = cdk.App()

# Leer configuración del contexto CDK (cdk.json o cdk deploy --context)
project = app.node.try_get_context("project") or "CGA"
env     = app.node.try_get_context("env")     or "PDN"
owner   = app.node.try_get_context("owner")   or "CloudOps"

stack = MiStack(app, f"{project}-Stack")

cdk.Tags.of(stack).add("Project",    project)
cdk.Tags.of(stack).add("Env",        env)
cdk.Tags.of(stack).add("Owner",      owner)
cdk.Tags.of(stack).add("CostCenter", f"{project}-{env}")
cdk.Tags.of(stack).add("ManagedBy",  "CDK")

app.synth()
```

Despliegue con contexto:
```bash
cdk deploy --context project=MI-APP --context env=DEV --context owner=equipo-backend
```

---

## 5. Consecuencias de no cumplir

El **Cloud Governance Agent** escanea periódicamente todos los recursos AWS y evalúa el cumplimiento de esta política.

Un recurso se considera **no conforme** si le falta al menos uno de los cuatro tags obligatorios (`Project`, `Env`, `Owner`, `CostCenter`).

### Impactos

- **Hallazgo de compliance** — Se genera un finding con severidad **MEDIUM** en el dashboard de governance.
- **Sin atribución de costos** — El recurso no puede ser asociado a ningún proyecto ni centro de costo, impidiendo el análisis de facturación por proyecto en AWS Cost Explorer.
- **Dificultad operacional** — Sin `Owner` no es posible identificar al responsable en caso de incidentes o recursos huérfanos.
- **Alertas automáticas** — El agente reporta los recursos no taggeados de forma regular, incrementando el ruido operacional.

### Proceso de remediación

1. Identificar el recurso reportado por el agente.
2. Agregar los tags faltantes (manual en consola o vía IaC).
3. Si el recurso está gestionado por CDK, corregir el stack y re-desplegar.
4. Verificar que el finding se cierre en el siguiente escaneo del agente.

---

## 6. Tabla de valores válidos e inválidos

| Tag | Valor Válido | Valor Inválido | Motivo del rechazo |
|-----|-------------|----------------|-------------------|
| `Project` | `CGA` | `cloud governance agent` | Espacios y minúsculas |
| `Project` | `MI-APP` | `mi app` | Espacios y minúsculas |
| `Env` | `PDN` | `production` | No es un valor del catálogo permitido |
| `Env` | `DEV` | `dev` | Minúsculas no permitidas |
| `Env` | `STG` | `staging` | No es un valor del catálogo permitido |
| `CostCenter` | `CGA-PDN` | `CGA PDN` | Espacio en el valor |
| `CostCenter` | `MIAPP-DEV` | `miapp-dev` | Minúsculas no permitidas |
| `Owner` | `CloudOps` | `cloud ops team` | Espacios; usar guión si es compuesto |
| `ManagedBy` | `CDK` | `aws-cdk` | Usar los valores estándar definidos |

---

## 7. Proyectos en la misma cuenta — Aislamiento por tags

La siguiente tabla muestra cómo distintos proyectos coexisten en la misma cuenta AWS usando tags para su aislamiento lógico y separación de costos.

| Proyecto | `Project` | `Env` | `CostCenter` | `Owner` |
|----------|-----------|-------|--------------|---------|
| Cloud Governance Agent | `CGA` | `PDN` | `CGA-PDN` | `CloudOps` |
| Mi Aplicación Web | `MI-APP` | `DEV` | `MIAPP-DEV` | `equipo-frontend` |
| API Backend | `BACKEND` | `STG` | `BACKEND-STG` | `equipo-backend` |
| Plataforma de Datos | `DATA-PLAT` | `PDN` | `DATAPLAT-PDN` | `equipo-datos` |

### Cómo usar los tags para filtrar en AWS Cost Explorer

1. Abrir **AWS Cost Explorer** → *Group by* → seleccionar `Tag: Project`.
2. Filtrar por `Tag: CostCenter` para ver el desglose de un proyecto específico.
3. Configurar **Cost Allocation Tags** en Billing → activar `Project`, `Env` y `CostCenter` como tags de asignación de costos (esto permite que aparezcan como dimensiones en Cost Explorer).

> **Nota:** Los Cost Allocation Tags deben activarse manualmente en la consola de AWS Billing una sola vez por cuenta. Sin esta activación, los tags existen en los recursos pero no se reflejan como dimensiones de filtrado en Cost Explorer.

---

## 8. Historial de cambios

| Versión | Fecha | Descripción | Autor |
|---------|-------|-------------|-------|
| 1.0 | 2025-07-15 | Versión inicial de la política | CloudOps / Kiro |
