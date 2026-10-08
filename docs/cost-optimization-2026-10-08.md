# Optimización de Costos AWS — 8 de Octubre 2026

## Resumen Ejecutivo

| Métrica | Valor |
|---|---|
| Costo mensual estimado **ANTES** | ~$167 USD |
| Costo mensual estimado **DESPUÉS** | <$1 USD |
| Ahorro logrado | ~$166 USD/mes (~99% de reducción) |
| Ahorro anual proyectado | ~$1,990 USD |
| Fecha de ejecución | 8 de octubre de 2026 |
| Stacks eliminados | 6 de 6 exitosamente |

---

## Contexto del Proyecto

El **cloud-governance-agent** es un sistema de auditoría continua de infraestructura AWS que opera sobre una arquitectura serverless compuesta por Lambda (Python 3.12), EventBridge, S3 y SNS. Su función principal es analizar recursos desplegados en la cuenta, detectar configuraciones inseguras, costos innecesarios y desviaciones respecto a buenas prácticas, generando reportes periódicos automatizados.

Los **stacks demo `CGA-Sample-*`** fueron creados el 7 de septiembre de 2026 con el propósito explícito de generar hallazgos intencionales que demostraran las capacidades de detección del agente: instancias RDS públicamente accesibles, EC2 sobredimensionadas, EIPs huérfanas, distribuciones CloudFront sin WAF, usuarios IAM sin MFA, entre otros. Cada recurso incluía comentarios como "hallazgo CGA intencional".

La decisión de eliminarlos se tomó el 8 de octubre de 2026, dado que su propósito de demostración ya había sido cumplido y estos stacks representaban el **99.9% del gasto total mensual** de la cuenta, generando un costo completamente innecesario para la operación del proyecto.

---

## Análisis de Costos — Septiembre 2026

### Desglose por Servicio

| Servicio | Costo Sep 2026 | % del Total |
|---|---|---|
| Amazon RDS | $130.25 | 77.6% |
| Amazon ELB (ALB) | $12.42 | 7.4% |
| Amazon EC2 – Compute | $11.47 | 6.8% |
| Amazon VPC | $11.04 | 6.6% |
| EC2 – Other (EBS, EIP) | $1.96 | 1.2% |
| AWS Secrets Manager | $0.61 | 0.4% |
| Otros (S3, Lambda, DynamoDB, etc.) | ~$0 | ~0% |
| **TOTAL** | **$167.78** | **100%** |

### Análisis del Gasto

Amazon RDS fue la fuente dominante de costos, representando el **77% del gasto total** ($130.25/mes). Este gasto provenía exclusivamente de las dos instancias RDS del stack `CGA-Sample-Database` (MySQL 8.0 y PostgreSQL 15.7, ambas en clase `db.t3.micro`). A pesar de no recibir tráfico real, las instancias en estado `available` generan cargo 24/7 por cómputo, almacenamiento y backups, lo que explica el monto elevado.

El restante 22% del gasto correspondía a los otros recursos demo: el ALB inactivo (`alb-idle-demo`), las instancias EC2 con utilización cercana al 2%, y la VPC con su EIP huérfana. La infraestructura core del agente (Lambda, EventBridge, S3, SNS, CloudWatch) operó dentro del free tier con costo efectivo de $0.

> ⚠️ Al ritmo observado en los primeros 8 días de octubre ($49.13), el mes proyectaba un gasto de ~$211 USD, un 26% mayor que septiembre, ya que RDS en estado `available` no se había detenido aún.

---

## Inventario de Recursos Eliminados

Los siguientes 6 stacks demo fueron identificados y eliminados. Todos habían sido creados el **7 de septiembre de 2026** con propósito de demostración.

| Stack | Recursos Principales | Costo Mensual Estimado |
|---|---|---|
| CGA-Sample-Database | 2x RDS (MySQL + PostgreSQL db.t3.micro), 1x DynamoDB, 2x Secrets Manager | ~$131/mes |
| CGA-Sample-Network | VPC, ALB, EIP huérfana, subnets, security groups | ~$31/mes |
| CGA-Sample-Compute | 3x EC2 t3.micro (2 running + 1 stopped), 2x Lambda, 3x EBS | ~$15/mes |
| CGA-Sample-Frontend | 2x CloudFront distributions, 2x S3 buckets | ~$0/mes |
| CGA-Sample-Storage | 4x S3 buckets, 1x EBS huérfano | ~$1/mes |
| CGA-Sample-IAM | Usuarios IAM sin MFA, access keys, políticas permisivas | ~$0/mes |

> **Nota:** Todos los stacks fueron creados el 7 de septiembre de 2026 con propósito de demostración. El stack `CGA-Sample-Database` con sus instancias RDS representaba el 77% del gasto mensual total de la cuenta.

---

## Acciones Realizadas

### Paso previo: Deshabilitar CloudFront

Antes de eliminar `CGA-Sample-Frontend`, fue necesario deshabilitar las 2 distribuciones CloudFront activas que habrían impedido la eliminación del stack. Se esperó a que ambas distribuciones alcanzaran estado `Deployed` antes de continuar.

| Distribution ID | Estado Original | Acción | Estado Final |
|---|---|---|---|
| EY7V9BY6D9983 | Enabled=true | UpdateDistribution → Enabled=false | Deployed, Enabled=false |
| E3E9JWI4UVRF7D | Enabled=true | UpdateDistribution → Enabled=false | Deployed, Enabled=false |

### Eliminación de stacks (hora local CST)

| # | Stack | Inicio | Fin | Duración | Resultado |
|---|---|---|---|---|---|
| 1 | CGA-Sample-Compute | 10:45:20 | 10:46:27 | ~1 min | ✅ Exitoso |
| 2 | CGA-Sample-Database | 10:46:34 | 10:53:46 | ~7 min | ✅ Exitoso |
| 3 | CGA-Sample-Frontend | 10:53:57 | 10:54:33 | ~36 seg | ✅ Exitoso |
| 4 | CGA-Sample-Storage | 10:54:40 | 10:55:16 | ~36 seg | ✅ Exitoso |
| 5 | CGA-Sample-Network | 10:55:23 | 10:57:00 | ~1.5 min | ✅ Exitoso |
| 6 | CGA-Sample-IAM | 10:57:06 | 10:58:13 | ~1 min | ✅ Exitoso |

**Total: 6 de 6 stacks eliminados exitosamente** — duración total del proceso: ~13 minutos (10:45–10:58 CST).

La eliminación de cada stack fue verificada mediante `aws cloudformation describe-stacks`, que retornó `ValidationError: Stack with id <nombre> does not exist`, confirmando la eliminación completa.

---

## Estado Post-Optimización

### Stacks activos en la cuenta

| Stack | Estado | Propósito |
|---|---|---|
| CloudGovernanceAgent | UPDATE_COMPLETE | Infraestructura core del agente |
| CDKToolkit | CREATE_COMPLETE | Bootstrap CDK (requerido para despliegues) |

### Costo mensual residual estimado

**< $1 USD/mes** — compuesto únicamente por la infraestructura core del agente:

| Recurso | Costo |
|---|---|
| Lambda `cloud-governance-agent` (512 MB, python3.12) | $0 (free tier: 1M requests/mes) |
| EventBridge Rule `cga-weekly-schedule` | $0 |
| SNS Topic `cga-lambda-alarms` | $0 |
| CloudWatch Alarm + Log Group (retención 90 días) | $0 |
| S3 `cga-reports-062560094883` (~1 MB, 11 objetos) | ~$0 |
| **TOTAL** | **~$0/mes** |

### Confirmación operacional

El stack `CloudGovernanceAgent` permanece en estado `UPDATE_COMPLETE`, confirmando que el agente de gobernanza está completamente operacional. Recursos verificados activos:
- Lambda: `cloud-governance-agent`
- S3 bucket de reportes: `cga-reports-062560094883`
- CloudWatch Log Group: `/aws/lambda/cloud-governance-agent`

---

## Recomendaciones Futuras

1. **Usar etiquetas de costo desde el inicio**: Todo recurso AWS debe tener etiquetas `Environment`, `Project`, `Owner`, `CostCenter` para facilitar el tracking. Sin estas etiquetas, atribuir costos a stacks o equipos requiere correlación manual costosa.

2. **AWS Budgets con alertas**: Configurar alerta a $10/mes y $50/mes para detección temprana de gastos inesperados. El costo de este proyecto alcanzó los $167/mes antes de ser detectado; una alerta a $10 habría disparado la revisión en la primera semana de septiembre.

3. **Ciclo de vida de recursos demo**: Los stacks de demostración deben tener una fecha de expiración documentada y preferiblemente usar AWS CloudFormation StackSets con TTL o un proceso automatizado de limpieza. Una práctica recomendada es agregar un tag `ExpiresOn: YYYY-MM-DD` y una regla en EventBridge que evalúe y notifique cuando se acerque esa fecha.

4. **RDS: usar instancias bajo demanda y destruir tras demos**: Nunca dejar RDS corriendo indefinidamente para demos; usar snapshots para restaurar cuando se necesite. Una instancia `db.t3.micro` RDS en estado `available` genera ~$65/mes aunque no reciba ninguna conexión.

5. **AWS Cost Explorer mensual**: Revisar costos el primer lunes de cada mes con el cloud-governance-agent. El agente ya está configurado con una regla EventBridge semanal (`cga-weekly-schedule`); sus reportes deben incluir comparativos mes a mes.

6. **CloudFormation Drift Detection**: Ejecutar periódicamente para detectar cambios manuales no autorizados. Los recursos creados fuera de CloudFormation no aparecen en los stacks y pueden generar costos ocultos difíciles de rastrear.

---

*Documento generado el 8 de octubre de 2026 como resultado del análisis de costos ejecutado por el cloud-governance-agent.*  
*Ejecutado por: Kiro AI Assistant + wf-coder*
