# ADR-001: Arquitectura Serverless con AWS Lambda

| Campo | Valor |
|---|---|
| **ID** | ADR-001 |
| **Título** | Arquitectura Serverless con AWS Lambda |
| **Estado** | Aceptado |
| **Fecha** | 2026-09-07 |
| **Autor** | Marcelo Dev |
| **Revisado por** | — |

---

## Contexto

El CGA necesita ejecutarse periódicamente (una vez por semana) y bajo demanda. El proceso de auditoría involucra consultar múltiples APIs de AWS, lo que implica tiempos de ejecución variables entre 2 y 15 minutos dependiendo de la cantidad de recursos en la cuenta.

Se requiere una solución que:
- No tenga costo cuando no está ejecutándose
- Escale sin intervención manual
- Sea fácil de desplegar y mantener
- No requiera administración de servidores

## Decisión

Usar **AWS Lambda** como motor de ejecución del agente, con un timeout de 900 segundos (15 minutos) y 512 MB de memoria.

## Alternativas Consideradas

### Opción A: Amazon EC2 (instancia dedicada)
- ✅ Sin límite de tiempo de ejecución
- ✅ Control total del entorno
- ❌ Costo fijo 24/7 aunque solo se use 15 min/semana (~$15-30/mes innecesarios)
- ❌ Requiere gestión de parches y mantenimiento del OS
- ❌ Sobredimensionado para la carga de trabajo

### Opción B: Amazon ECS / Fargate (tarea programada)
- ✅ Sin límite de tiempo de ejecución
- ✅ Sin administración de servidores
- ❌ Mayor complejidad de configuración (task definition, cluster, VPC)
- ❌ Costo mayor que Lambda para ejecuciones cortas/infrecuentes
- ❌ Tiempo de arranque más lento (cold start de contenedor)

### Opción C: AWS Lambda ✅ ELEGIDA
- ✅ Costo por invocación — prácticamente $0 para 1 ejecución/semana
- ✅ Timeout de 15 minutos — suficiente para el proceso de auditoría
- ✅ Integración nativa con EventBridge, IAM, CloudWatch
- ✅ Despliegue simple vía CDK
- ✅ Sin administración de infraestructura
- ❌ Límite de 15 minutos (aceptable para el scope actual)
- ❌ Límite de 512 MB de almacenamiento efímero (no requerimos más)

### Opción D: AWS Step Functions + Lambda
- ✅ Orquestación visual de pasos
- ✅ Reintentos automáticos por paso
- ❌ Mayor complejidad para el MVP
- ❌ Costo adicional por transiciones de estado
- ⚠️ Considerado para v2 si la auditoría crece en complejidad

## Consecuencias

**Positivas:**
- Costo operativo mínimo (< $1/mes estimado)
- Despliegue y actualizaciones simples
- Logs y métricas integrados con CloudWatch sin configuración adicional

**Negativas / Riesgos:**
- Si la cuenta tiene miles de recursos, el proceso podría acercarse al límite de 15 minutos. Mitigación: ejecución paralela de checkers con `ThreadPoolExecutor`.
- En cuentas multi-región con muchas regiones habilitadas, considerar particionamiento por región en v2.

## Referencias
- [AWS Lambda Quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [Lambda vs Fargate cost comparison](https://aws.amazon.com/lambda/pricing/)
