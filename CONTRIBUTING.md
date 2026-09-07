# Guía de Contribución — Cloud Governance Agent (CGA)

Gracias por tu interés en contribuir al CGA. Este documento explica cómo participar de forma efectiva.

---

## Tabla de Contenidos

1. [Código de Conducta](#código-de-conducta)
2. [¿Cómo contribuir?](#cómo-contribuir)
3. [Configuración del entorno de desarrollo](#configuración-del-entorno-de-desarrollo)
4. [Estándares de código](#estándares-de-código)
5. [Agregar un nuevo checker](#agregar-un-nuevo-checker)
6. [Tests](#tests)
7. [Pull Requests](#pull-requests)
8. [Reporte de bugs](#reporte-de-bugs)

---

## Código de Conducta

Este proyecto adopta un ambiente de colaboración respetuoso. Se espera:
- Lenguaje inclusivo y profesional en todas las interacciones
- Retroalimentación constructiva orientada al código, no a las personas
- Apertura a diferentes perspectivas y enfoques técnicos

---

## ¿Cómo contribuir?

Las contribuciones más valiosas son:

| Tipo | Ejemplos |
|---|---|
| **Nuevos checkers** | Agregar auditoría de EKS, SQS, Bedrock, API Gateway |
| **Mejora de checks existentes** | Refinar umbrales, agregar nuevos casos de detección |
| **Corrección de bugs** | Errores en cálculo de costos, falsos positivos |
| **Documentación** | Mejorar README, agregar ejemplos de reportes |
| **Tests** | Aumentar cobertura de tests unitarios |
| **Infraestructura** | Mejorar el stack CDK, agregar outputs útiles |

---

## Configuración del Entorno de Desarrollo

### Prerrequisitos
- Python 3.12+
- AWS CLI v2 configurado
- Node.js 18+ (requerido por CDK)
- AWS CDK v2: `npm install -g aws-cdk`

### Pasos

```bash
# 1. Fork y clonar el repositorio
git clone https://github.com/tu-usuario/cloud-governance-agent.git
cd cloud-governance-agent

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Linux/Mac

# 3. Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# 4. Verificar que los tests pasan
pytest tests/ -v
```

### Dependencias de desarrollo (`requirements-dev.txt`)
```
boto3==1.34.0
moto[all]==5.0.0
pytest==8.0.0
pytest-cov==5.0.0
black==24.0.0
flake8==7.0.0
aws-cdk-lib==2.150.0
constructs==10.3.0
```

---

## Estándares de Código

### Estilo
- Seguir **PEP 8** estrictamente
- Formatear con **black** antes de cada commit: `black src/ tests/`
- Validar con **flake8**: `flake8 src/ tests/ --max-line-length=100`

### Convenciones de nombres
- Archivos: `snake_case.py`
- Clases: `PascalCase`
- Funciones y variables: `snake_case`
- Constantes: `UPPER_SNAKE_CASE`

### Docstrings
Todas las clases y métodos públicos deben tener docstring en formato Google:

```python
def run(self) -> List[Finding]:
    """Ejecuta todos los checks del módulo.

    Returns:
        List[Finding]: Lista de hallazgos encontrados. Lista vacía si no hay hallazgos.

    Raises:
        ClientError: Si la API de AWS retorna un error no recuperable.
    """
```

### Logging
Usar siempre el logger estructurado del proyecto, nunca `print()`:

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Iniciando IAM checker", extra={"account_id": self.account_id})
```

---

## Agregar un Nuevo Checker

Esta es la contribución más común. Sigue estos pasos:

### 1. Crear el archivo del checker

```bash
# Ejemplo: agregar auditoría de Amazon SQS en dominio FinOps
touch src/checkers/finops/sqs_checker.py
```

### 2. Implementar la clase heredando de `BaseChecker`

```python
# src/checkers/finops/sqs_checker.py
from typing import List
from src.checkers import BaseChecker
from src.core.models import Finding


class SQSFinOpsChecker(BaseChecker):
    """Audita colas SQS en busca de recursos subutilizados o sin uso."""

    def run(self) -> List[Finding]:
        """Ejecuta todos los checks de SQS FinOps."""
        findings = []
        findings.extend(self._check_empty_queues())
        return findings

    def _check_empty_queues(self) -> List[Finding]:
        """Detecta colas SQS sin mensajes en los últimos 30 días."""
        findings = []
        # ... implementación
        return findings
```

### 3. Registrar el checker en el orquestador

En `src/handler.py`, agregar el nuevo checker al grupo correspondiente:

```python
from src.checkers.finops.sqs_checker import SQSFinOpsChecker

# En la lista de checkers de FinOps:
finops_checkers = [
    EC2FinOpsChecker(session, config),
    # ... otros checkers
    SQSFinOpsChecker(session, config),   # <-- agregar aquí
]
```

### 4. Agregar tests unitarios

```bash
touch tests/unit/checkers/finops/test_sqs_checker.py
```

### 5. Documentar el nuevo check en README.md

Agregar una fila a la tabla de checks del dominio correspondiente.

### 6. Actualizar CHANGELOG.md

Agregar una entrada en la sección `[Unreleased]`.

---

## Tests

### Ejecutar todos los tests
```bash
pytest tests/ -v
```

### Ejecutar con cobertura
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Estándar mínimo de cobertura
- Cada nuevo checker debe tener tests que cubran al menos:
  - ✅ Caso conforme: recurso que NO genera hallazgo
  - ✅ Caso no conforme: recurso que SÍ genera hallazgo
  - ✅ Caso edge: recurso sin tags, lista vacía de recursos

### Uso de moto para mockear AWS

```python
import pytest
import boto3
from moto import mock_aws
from src.checkers.security.iam_checker import IAMChecker

@mock_aws
def test_iam_user_without_mfa_generates_finding():
    # Arrange: crear usuario IAM sin MFA con moto
    iam = boto3.client("iam", region_name="us-east-1")
    iam.create_user(UserName="test-user")

    # Act
    checker = IAMChecker(session=boto3.Session(), config={"region": "us-east-1", "account_id": "123456789012"})
    findings = checker.run()

    # Assert
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].category == "iam"
```

---

## Pull Requests

### Proceso

1. Crea un branch desde `main` con nombre descriptivo:
   ```bash
   git checkout -b feature/add-sqs-checker
   git checkout -b fix/ec2-cpu-calculation
   git checkout -b docs/improve-readme
   ```

2. Realiza los cambios siguiendo los estándares de código

3. Asegúrate de que los tests pasan y el código está formateado:
   ```bash
   black src/ tests/
   flake8 src/ tests/ --max-line-length=100
   pytest tests/ -v
   ```

4. Actualiza `CHANGELOG.md` en la sección `[Unreleased]`

5. Crea el Pull Request con:
   - **Título**: conciso, máximo 70 caracteres (ej: `feat: add SQS FinOps checker`)
   - **Descripción**: qué cambió, por qué, cómo se testeó
   - **Labels**: `feature`, `bug`, `docs`, `tests`

### Prefijos de commits (Conventional Commits)

```
feat:     nueva funcionalidad
fix:      corrección de bug
docs:     cambios en documentación
test:     agregar o modificar tests
refactor: refactorización sin cambio funcional
chore:    cambios en build, dependencias, etc.
```

Ejemplo: `feat: add SQS empty queue checker for FinOps domain`

---

## Reporte de Bugs

Usa los [GitHub Issues](https://github.com/tu-usuario/cloud-governance-agent/issues) con la siguiente información:

```markdown
## Descripción del bug
Descripción clara y concisa del problema.

## Pasos para reproducir
1. Configurar X
2. Ejecutar el agente
3. Ver el error en Y

## Comportamiento esperado
Lo que debería ocurrir.

## Comportamiento actual
Lo que ocurre actualmente.

## Entorno
- Python version: 3.12.x
- boto3 version: x.x.x
- Región AWS: us-east-1
- Tipo de ejecución: scheduled / on-demand

## Logs relevantes
```
[pegar logs de CloudWatch aquí]
```
```

---

## Preguntas

Para preguntas generales, usa [GitHub Discussions](https://github.com/tu-usuario/cloud-governance-agent/discussions) en lugar de Issues.
