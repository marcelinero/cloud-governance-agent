## Descripción

<!-- Qué cambió y por qué. Enlaza el issue relacionado si aplica (ej: Closes #12). -->

## Tipo de cambio

- [ ] `feat` — nueva funcionalidad
- [ ] `fix` — corrección de bug
- [ ] `docs` — documentación
- [ ] `test` — tests
- [ ] `refactor` — refactorización sin cambio funcional
- [ ] `chore` — build, dependencias, etc.

## ¿Cómo se probó?

<!-- Comandos ejecutados, resultados de pytest, evidencia. -->

```bash
pytest tests/ -v
```

## Checklist

- [ ] El código sigue PEP 8 y está formateado con `black`
- [ ] `flake8` no reporta errores nuevos
- [ ] Los tests pasan localmente
- [ ] Se agregaron tests para el cambio (si aplica)
- [ ] Se actualizó `CHANGELOG.md` en la sección `[Unreleased]`
- [ ] Se actualizó la documentación (README/checks) si aplica
- [ ] No se exponen datos sensibles (account IDs reales, nombres, credenciales)
