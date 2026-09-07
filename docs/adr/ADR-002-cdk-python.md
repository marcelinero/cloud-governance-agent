# ADR-002: AWS CDK con Python como herramienta IaC

| Campo | Valor |
|---|---|
| **ID** | ADR-002 |
| **Título** | AWS CDK con Python como herramienta de Infraestructura como Código |
| **Estado** | Aceptado |
| **Fecha** | 2026-09-07 |
| **Autor** | Marcelo Dev |
| **Revisado por** | — |

---

## Contexto

El proyecto requiere desplegar varios recursos AWS (Lambda, S3, IAM Role, EventBridge, CloudWatch, SNS) de forma reproducible, versionada y automatizable. La infraestructura debe:

- Poder desplegarse en cualquier cuenta AWS con mínima configuración
- Ser legible y mantenible por un desarrollador Python
- Estar versionada en el mismo repositorio que el código de la aplicación
- Facilitar la publicación del proyecto en GitHub como referencia

## Decisión

Usar **AWS CDK v2 con Python** como herramienta de Infraestructura como Código.

## Alternativas Consideradas

### Opción A: AWS CloudFormation (YAML/JSON nativo)
- ✅ Herramienta nativa de AWS, sin dependencias adicionales
- ✅ Soportado directamente en la consola AWS
- ❌ Sintaxis YAML verbosa — una Lambda simple requiere 150+ líneas
- ❌ Lenguaje diferente al del proyecto (YAML vs Python)
- ❌ Sin autocompletado ni validación de tipos en el IDE
- ❌ Difícil de reutilizar lógica (sin loops ni condicionales reales)

### Opción B: Terraform (HashiCorp)
- ✅ Multi-cloud — útil si el proyecto se expande a Azure/GCP
- ✅ Gran ecosistema y comunidad
- ❌ Requiere instalar Terraform CLI (dependencia externa)
- ❌ Lenguaje HCL — diferente al del proyecto
- ❌ Gestión de estado (`terraform.tfstate`) requiere backend remoto (S3+DynamoDB)
- ❌ Curva de aprendizaje adicional para el lector del repositorio

### Opción C: AWS CDK v2 con Python ✅ ELEGIDA
- ✅ **Mismo lenguaje que la aplicación** — un solo lenguaje en todo el repositorio
- ✅ Genera CloudFormation por debajo — nativo de AWS, sin estado externo
- ✅ Autocompletado e intellisense en el IDE
- ✅ Constructs de alto nivel — menos código para el mismo resultado
- ✅ Fácil de leer para la publicación en GitHub y LinkedIn
- ✅ Mantenido por AWS, primera clase en el ecosistema
- ❌ Requiere Node.js instalado (solo para el CLI de CDK)
- ❌ Ligera curva de aprendizaje para quienes conocen solo CloudFormation

### Opción D: AWS SAM (Serverless Application Model)
- ✅ Especializado para aplicaciones serverless
- ✅ Permite testing local de Lambda
- ❌ Limitado a serverless — no cubre todos los recursos del proyecto (ej: alarmas CloudWatch)
- ❌ Sintaxis YAML — misma desventaja que CloudFormation

## Consecuencias

**Positivas:**
- Un solo lenguaje (Python) para toda la solución — más fácil de mantener y publicar
- CDK constructs manejan defaults seguros (ej: S3 block public access automático)
- El `cdk diff` permite ver cambios antes de aplicarlos — equivalente a `terraform plan`
- El código CDK es más conciso y expresivo que CloudFormation equivalente

**Negativas / Riesgos:**
- Requiere Node.js como dependencia para el CLI de CDK (documentado en prerrequisitos)
- La curva de aprendizaje para CDK es de 1-2 días para alguien con experiencia en Python

## Referencias
- [AWS CDK v2 Developer Guide](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
- [CDK Python Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [CDK vs CloudFormation vs Terraform comparison](https://aws.amazon.com/blogs/developer/getting-started-with-the-aws-cloud-development-kit-and-python/)
