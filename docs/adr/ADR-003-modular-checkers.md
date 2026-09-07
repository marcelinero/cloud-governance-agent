# ADR-003: Checkers Modulares por Servicio AWS

| Campo | Valor |
|---|---|
| **ID** | ADR-003 |
| **Título** | Diseño de checkers modulares independientes por servicio AWS |
| **Estado** | Aceptado |
| **Fecha** | 2026-09-07 |
| **Autor** | Marcelo Dev |
| **Revisado por** | — |

---

## Contexto

El agente necesita auditar más de 10 servicios AWS diferentes, cada uno con múltiples checks de seguridad y/o costos. Se necesita decidir cómo organizar esta lógica de auditoría para que sea:

- Fácil de extender con nuevos servicios sin riesgo de romper los existentes
- Testeable de forma independiente con mocks de AWS (moto)
- Legible para alguien que quiera entender qué audita el agente
- Ejecutable en paralelo para optimizar el tiempo total de ejecución

## Decisión

Implementar **un checker por servicio AWS**, organizados en carpetas por dominio (`security/`, `finops/`, `compliance/`), todos heredando de una clase abstracta `BaseChecker`.

## Alternativas Consideradas

### Opción A: Un único archivo con toda la lógica
- ✅ Simple al principio
- ❌ Archivo de miles de líneas — inmantenible
- ❌ Imposible testear un check sin ejecutar todos
- ❌ Cualquier error rompe toda la auditoría
- ❌ Conflictos de merge en git si varios colaboradores trabajan en paralelo

### Opción B: Un checker por dominio (Security, FinOps, Compliance)
- ✅ Solo 3 archivos — simple de navegar
- ❌ Cada archivo sigue siendo grande (500+ líneas)
- ❌ Mezcla servicios muy distintos (IAM + CloudFront + RDS en un mismo archivo)
- ❌ Difícil de testear servicios individuales

### Opción C: Un checker por servicio AWS ✅ ELEGIDA
- ✅ **Responsabilidad única** — cada archivo audita exactamente un servicio
- ✅ **Extensible** — agregar `eks_checker.py` no toca ningún otro archivo
- ✅ **Testeable** — se puede mockear solo el servicio relevante con moto
- ✅ **Fault isolation** — si `cloudfront_checker.py` falla, los demás siguen ejecutando
- ✅ **Legible** — el nombre del archivo indica exactamente qué audita
- ❌ Más archivos que manejar (~13 checkers para el MVP)
- ❌ Requiere una convención clara de nomenclatura

### Opción D: Checkers configurados via YAML/JSON (data-driven)
- ✅ Agregar checks sin código — solo editar un archivo de configuración
- ❌ Lógica compleja (métricas de CloudWatch, cálculos de costos) no encaja en YAML
- ❌ Difícil de debuggear
- ⚠️ Considerado para checks simples de tagging en v2

## Diseño de la Interfaz Base

```python
from abc import ABC, abstractmethod
from typing import List
from src.core.models import Finding

class BaseChecker(ABC):
    def __init__(self, session, config: dict):
        self.session = session      # boto3 session
        self.config = config        # variables de entorno / umbrales
        self.account_id = config["account_id"]
        self.region = config["region"]

    @abstractmethod
    def run(self) -> List[Finding]:
        """Ejecuta todos los checks y retorna lista de hallazgos."""
        pass

    def _build_finding(self, **kwargs) -> Finding:
        """Helper para construir un Finding con valores por defecto."""
        pass
```

## Convención de Nomenclatura

```
src/checkers/
  security/
    {servicio}_checker.py      # ej: iam_checker.py, s3_checker.py
  finops/
    {servicio}_checker.py      # ej: ec2_checker.py, rds_checker.py
  compliance/
    {aspecto}_checker.py       # ej: tagging_checker.py
```

Si un servicio tiene checks en dos dominios (ej: RDS en seguridad y en FinOps), se crea un checker por dominio: `security/rds_checker.py` y `finops/rds_checker.py`.

## Consecuencias

**Positivas:**
- Cada checker puede desarrollarse, testearse y desplegarse de forma independiente
- El orquestador solo necesita conocer la interfaz `BaseChecker.run()` — no los detalles
- Agregar soporte para EKS, Bedrock, SQS, etc. en v2 es trivial
- La fault isolation evita que un error de API en un servicio detenga toda la auditoría

**Negativas / Riesgos:**
- Con 13+ checkers, el número de archivos puede parecer elevado para un proyecto pequeño. Mitigación: la estructura de carpetas por dominio mantiene la navegabilidad.
- Algunos servicios comparten lógica (obtener tags, calcular costos). Mitigación: helpers en `BaseChecker` y `utils/aws_client.py`.

## Referencias
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
- [moto — AWS mock library for Python](https://docs.getmoto.org/en/latest/)
