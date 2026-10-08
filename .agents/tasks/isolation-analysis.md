# Análisis de Aislamiento — Cloud Governance Agent en Cuenta AWS Compartida

**Fecha:** 2026-10-08  
**Autor:** Kiro (investigación automatizada, solo lectura)  
**Stack analizado:** `CloudGovernanceAgent` (us-east-1, cuenta `062560094883`)  
**Estado del stack:** `UPDATE_COMPLETE`

---

## Respuesta Directa

**Sí puedes desplegar otros proyectos en la misma cuenta sin conflictos — con condiciones.**

El Cloud Governance Agent tiene un nivel de aislamiento **bueno pero incompleto**. Los recursos más críticos (S3 bucket, Lambda, IAM Role, EventBridge rule, SNS topic) usan el prefijo `cga-` o el nombre `cloud-governance-agent`, lo que previene colisiones directas de nombres. Sin embargo, hay tres puntos de riesgo concretos que se deben tener en cuenta al agregar otros proyectos, descritos en la sección de riesgos.

---

## Evidencia Recopilada

### 1. Nombres de recursos (prefijos y unicidad)

Recursos físicos confirmados por `ListStackResources` sobre el stack `CloudGovernanceAgent`:

| Recurso lógico CDK | Nombre físico en AWS | Tipo |
|---|---|---|
| `ReportsBucket4E7C5994` | `cga-reports-062560094883` | S3 Bucket |
| `CgaLambdaRole5C7634BB` | `cga-lambda-role` | IAM Role |
| `CgaLambdaRoleDefaultPolicy51C82731` | `Cloud-CgaLa-1UocmpWvMMrd` | IAM Policy (auto-generado) |
| `CgaOrchestratorD605F1D9` | `cloud-governance-agent` | Lambda Function |
| `CgaLogGroup2E4A3DAF` | `/aws/lambda/cloud-governance-agent` | CloudWatch Log Group |
| `CgaScheduleRuleFC0965D8` | `cga-weekly-schedule` | EventBridge Rule |
| `CgaAlarmTopicAEB69EFF` | `cga-lambda-alarms` | SNS Topic (ARN: `...:cga-lambda-alarms`) |
| `CgaErrorAlarmE4B98C1F` | `CGA-Lambda-Errors` | CloudWatch Alarm |

**Análisis de prefijos:**
- El bucket S3 usa `cga-reports-{account-id}` → el `account-id` como sufijo garantiza unicidad global de S3. ✅
- El IAM Role usa `cga-lambda-role` → el prefijo `cga-` es específico. ✅
- La Lambda usa `cloud-governance-agent` (sin prefijo `cga-`). ⚠️ Nombre legible pero verboso, no hay riesgo de colisión siempre que otro proyecto no use el mismo nombre exacto.
- EventBridge rule: `cga-weekly-schedule` → prefijado. ✅
- SNS topic: `cga-lambda-alarms` → prefijado. ✅
- CloudWatch alarm: `CGA-Lambda-Errors` → prefijado con `CGA-`. ✅
- La IAM Policy inline recibe nombre auto-generado por CDK (`Cloud-CgaLa-1UocmpWvMMrd`), que no es legible pero tampoco colisiona. ✅

**Fuente en código:** `infrastructure/stacks/cga_stack.py`, líneas `role_name="cga-lambda-role"`, `function_name="cloud-governance-agent"`, `rule_name="cga-weekly-schedule"`, `topic_name="cga-lambda-alarms"`, `alarm_name="CGA-Lambda-Errors"`, `bucket_name=f"cga-reports-{self.account}"`.

---

### 2. IAM Roles y Policies — scope y naming

El rol IAM tiene nombre **explícito y con prefijo**: `cga-lambda-role`.

Tags confirmados por `iam:GetRole`:
```json
[
  {"Key": "Project",    "Value": "cloud-governance-agent"},
  {"Key": "Repository", "Value": "github.com/marcelinero/cloud-governance-agent"},
  {"Key": "ManagedBy",  "Value": "CDK"}
]
```

El path del rol es `/` (raíz de IAM), lo cual es estándar. **No hay paths dedicados por proyecto** (ej. `/cga/`), lo que no genera conflictos pero sí reduce la legibilidad en cuentas con muchos roles.

Las permission statements usan SIDs prefijados con `Cga*` (ej. `CgaEC2ReadOnly`, `CgaS3PutReports`, `CgaDynamoDBReadOnly`), lo que facilita la auditoría de qué rol tiene qué permiso.

⚠️ **Riesgo menor**: `AWSLambdaBasicExecutionRole` se adjunta como managed policy. Esta es una AWS-managed policy que puede ser usada por múltiples roles simultáneamente — no es exclusiva del CGA, lo cual es correcto.

---

### 3. Variables de entorno vs. valores hardcodeados

La Lambda fue inspeccionada con `lambda:GetFunction`. Variables de entorno confirmadas:

```
AWS_ACCOUNT_NAME, REPORTS_BUCKET, AUDIT_EMAIL, SECURITY_EMAIL,
KEY_AGE_DAYS_THRESHOLD, CPU_THRESHOLD_PERCENT, FINOPS_EMAIL,
LOG_LEVEL, SES_SENDER_EMAIL, STOPPED_DAYS_THRESHOLD
```

**No hay valores hardcodeados en el código Lambda.** Toda la configuración se inyecta desde CDK context (`cdk.json`) vía variables de entorno. ✅

La única excepción es el nombre del log group `/aws/lambda/cloud-governance-agent`, que está hardcodeado en el stack CDK pero es determinístico y único.

---

### 4. S3 Bucket y DynamoDB — colisión de nombres

**S3 Bucket:** `cga-reports-062560094883`  
El sufijo es el account-id de la cuenta (`062560094883`), que es único por definición. Este bucket no puede colisionar con ningún otro proyecto desplegado en la misma cuenta porque los nombres de S3 son globalmente únicos y este ya está registrado. ✅

**DynamoDB:** El CGA no crea ninguna tabla DynamoDB propia. El `CgaDynamoDBReadOnly` en la policy es un permiso de lectura sobre tablas ajenas que el agente audita, no sobre una tabla propia. ✅ Sin riesgo de colisión.

---

### 5. Aislamiento de red (VPC, Security Groups)

Confirmado por `lambda:GetFunction`:
```json
"vpc_config": {
  "SubnetIds": [],
  "SecurityGroupIds": [],
  "VpcId": ""
}
```

**La Lambda NO está en ninguna VPC.** Se ejecuta en la infraestructura serverless de AWS con acceso a internet y a los endpoints públicos de las APIs de AWS (IAM, EC2, S3, Cost Explorer, etc.).

Esto tiene dos implicaciones:
1. **Sin aislamiento de red** entre el CGA y otros proyectos. No hay VPC dedicada, no hay security groups propios. La Lambda accede a toda la cuenta vía IAM, no vía red.
2. **Es apropiado para su caso de uso**: el CGA solo llama APIs públicas de AWS. Ponerlo en VPC añadiría complejidad sin beneficio de seguridad real.

No hay riesgo de conflicto de red con otros proyectos porque no ocupa subnets, no tiene security groups, y no escucha en ningún puerto.

---

### 6. Stack CDK — namespace, environment tags, separación de stacks

**Stack name:** `CloudGovernanceAgent` (único en la cuenta).  

Tags a nivel de toda la aplicación CDK (aplicados a todos los recursos):
```python
cdk.Tags.of(app).add("ManagedBy",  "CDK")
cdk.Tags.of(app).add("Project",    "cloud-governance-agent")
cdk.Tags.of(app).add("Repository", "github.com/marcelinero/cloud-governance-agent")
```

Confirmado en Lambda y S3 por `ListTags` y `GetBucketTagging`.

**Lo que falta:** No hay tag `Environment` (prod/dev/staging) ni `CostCenter`. Los tags existentes permiten identificar el proyecto pero no diferenciar entornos si se desplegara el CGA en la misma cuenta para dev y prod.

La arquitectura usa **un único stack** para todos los recursos. No hay separación por capas (networking, compute, storage en stacks separados). Para el alcance actual (agente con ~10 recursos), esto es razonable pero limita la flexibilidad si el proyecto crece.

---

### 7. EventBridge Rules y CloudWatch Alarms — unicidad

- EventBridge rule: `cga-weekly-schedule` (prefijado con `cga-`). ✅
- CloudWatch alarm: `CGA-Lambda-Errors` (prefijado con `CGA-`). ✅
- Log group: `/aws/lambda/cloud-governance-agent` (convención estándar de Lambda). ✅

No hay riesgo de colisión de nombres con otros proyectos siempre que los demás proyectos sigan sus propias convenciones de naming.

---

### 8. Documentación de multi-tenancy / multi-proyecto

Revisados: `docs/architecture/overview.md`, `docs/adr/ADR-001`, `ADR-002`, `ADR-003`.

No existe documentación sobre multi-tenancy, coexistencia de proyectos, o estrategia de múltiples stacks en la misma cuenta. El documento `overview.md` menciona "Multi-cuenta" como roadmap v2 (via STS AssumeRole), pero no aborda el escenario de múltiples proyectos en la misma cuenta.

---

### 9. Recursos físicos confirmados (resumen)

Todos los recursos del stack `CloudGovernanceAgent` activo en la cuenta `062560094883`:

| Nombre físico | Tipo | Prefijo CGA? |
|---|---|---|
| `cga-reports-062560094883` | S3 Bucket | ✅ sí |
| `cga-lambda-role` | IAM Role | ✅ sí |
| `Cloud-CgaLa-1UocmpWvMMrd` | IAM Policy | ⚠️ auto-generado |
| `cloud-governance-agent` | Lambda Function | ⚠️ parcial |
| `/aws/lambda/cloud-governance-agent` | CloudWatch Log Group | ✅ sí |
| `cga-weekly-schedule` | EventBridge Rule | ✅ sí |
| `cga-lambda-alarms` | SNS Topic | ✅ sí |
| `CGA-Lambda-Errors` | CloudWatch Alarm | ✅ sí |

---

### 10. Tags por recurso confirmados (AWS Resource Groups Tagging)

Tags consistentes confirmados en Lambda, S3, IAM Role:
- `Project: cloud-governance-agent`
- `Repository: github.com/marcelinero/cloud-governance-agent`
- `ManagedBy: CDK`
- `aws:cloudformation:stack-name: CloudGovernanceAgent` (auto-AWS)
- `aws:cloudformation:logical-id: <logical-id>` (auto-AWS)

---

## Conclusiones

### ¿Puedes desplegar otro proyecto en la misma cuenta sin conflictos?

**Sí, con las siguientes condiciones y advertencias:**

#### Puntos seguros ✅

1. **El bucket S3** (`cga-reports-062560094883`) usa el account-id como sufijo → imposible que otro proyecto colisione accidentalmente.
2. **El IAM Role** (`cga-lambda-role`) tiene nombre único con prefijo — no interferirá con roles de otros proyectos si estos siguen convenciones similares.
3. **EventBridge, SNS, CloudWatch** — todos prefijados con `cga-` o `CGA-`. Solo habría colisión si otro proyecto usara exactamente esos nombres.
4. **Sin VPC ni Security Groups propios** → no hay recursos de red que puedan superponerse o interferir con las VPCs de otros proyectos.
5. **Sin DynamoDB propia** → no hay tabla que pueda colisionar.
6. **CDK stack separado** → el CGA vive en su propio CloudFormation stack, completamente aislado del ciclo de vida de otros stacks.

#### Riesgos a gestionar ⚠️

**Riesgo 1 — Nombre de Lambda genérico:**  
El nombre `cloud-governance-agent` (sin prefijo `cga-`) es descriptivo pero si otro desarrollador intenta crear una Lambda con ese mismo nombre en la misma cuenta y región, habrá conflicto. Es improbable pero posible. Recomendado: renombrar a `cga-orchestrator` en la próxima actualización.

**Riesgo 2 — IAM permissions de amplio alcance:**  
El rol `cga-lambda-role` tiene permisos `resources: ["*"]` en casi todos sus statements (EC2, RDS, IAM, S3, Lambda, CloudFront, CloudTrail, CloudWatch, Cost Explorer, SES, DynamoDB, ELB). Esto es intencional para un agente de auditoría de cuenta completa, pero significa que el CGA puede leer metadata de los recursos de **cualquier otro proyecto** desplegado en la cuenta. No es un riesgo de modificación (todos son read-only excepto `s3:PutObject` en su propio bucket), pero sí de visibilidad de datos.

**Riesgo 3 — Sin tag `Environment`:**  
Si en el futuro se despliegan múltiples instancias del CGA (ej. una para producción y una para staging en la misma cuenta), los recursos no tendrán diferenciación por entorno y la gestión de costos por ambiente se complicará.

---

## Recomendaciones

Ordenadas de mayor a menor impacto:

### Recomendación 1 — Agregar tag `Environment` (prioridad: ALTA)

En `infrastructure/app.py`, agregar:
```python
cdk.Tags.of(app).add("Environment", "production")
cdk.Tags.of(app).add("CostCenter",  "OPS-001")
```
Esto permite filtrar costos por entorno en Cost Explorer y alinea al CGA con las mismas buenas prácticas que él mismo audita en otros recursos.

### Recomendación 2 — Renombrar la Lambda (prioridad: MEDIA)

En `infrastructure/stacks/cga_stack.py`, cambiar:
```python
function_name="cloud-governance-agent"  # actual
# a:
function_name="cga-orchestrator"        # recomendado
```
Esto hace el naming 100% consistente con el resto de recursos (`cga-*`) y elimina el riesgo teórico de colisión de nombre.

### Recomendación 3 — Usar IAM path `/cga/` para el rol (prioridad: BAJA)

En `infrastructure/stacks/cga_stack.py`:
```python
lambda_role = iam.Role(
    self, "CgaLambdaRole",
    role_name="cga-lambda-role",
    path="/cga/",               # <- agregar esto
    ...
)
```
Permite usar condiciones `iam:ResourceTag` o path-based policies para agrupar roles por proyecto en una cuenta con muchos proyectos.

### Recomendación 4 — Documentar la estrategia de co-existencia (prioridad: BAJA)

Crear `docs/multi-project.md` que establezca:
- Convención de prefijos por proyecto (ej. `cga-`, `myapp-`, etc.)
- Tags requeridos para todos los proyectos: `Project`, `Environment`, `CostCenter`, `Owner`
- Regla: nunca usar `resources: ["*"]` sin al menos un Condition de `aws:ResourceTag`

### Para desplegar un nuevo proyecto — guía de convivencia

Al desplegar cualquier otro stack en la misma cuenta:

1. **Usar prefijo único** en todos los nombres de recursos físicos (ej. `myproject-*`).
2. **Usar un CDK stack name separado** (ej. `MyProjectStack`), nunca `CloudGovernanceAgent`.
3. **No crear un rol llamado** `cga-lambda-role` ni un bucket llamado `cga-reports-*`.
4. **Aplicar los tags obligatorios**: `Project`, `Environment`, `Owner`, `CostCenter`.
5. **El CGA auditará automáticamente el nuevo proyecto** al ejecutarse el lunes siguiente — esto es un beneficio, no un problema. Los recursos sin tags recibirán findings de compliance.

---

## Resumen Ejecutivo

| Dimensión | Estado | Nivel de riesgo |
|---|---|---|
| Naming de S3 | `cga-reports-{account-id}` — globalmente único | 🟢 Bajo |
| Naming de IAM | `cga-lambda-role` con prefijo explícito | 🟢 Bajo |
| Naming de Lambda | `cloud-governance-agent` sin prefijo corto | 🟡 Medio |
| Naming de EventBridge/SNS/CW | Todos prefijados con `cga-`/`CGA-` | 🟢 Bajo |
| Aislamiento de red | Sin VPC — no aplica para este caso de uso | 🟢 No aplica |
| Variables de entorno | 100% configurables vía CDK context | 🟢 Bajo |
| Tags de proyecto | `Project`, `Repository`, `ManagedBy` presentes | 🟡 Faltan `Environment`, `CostCenter` |
| Separación de stacks | Stack único bien aislado por CloudFormation | 🟢 Bajo |
| Permisos IAM scope | `resources: ["*"]` en read-only — amplio pero apropiado | 🟡 Visible por diseño |
| Documentación multi-proyecto | No existe | 🟡 Gap de documentación |

**Veredicto final:** La arquitectura del CGA está diseñada razonablemente para coexistir en una cuenta compartida. Los riesgos existentes son menores y están en la categoría de buenas prácticas de naming/tagging, no de conflictos funcionales. Puedes desplegar otros proyectos en la misma cuenta hoy mismo, siempre que cada nuevo proyecto use sus propios prefijos de nombres.
