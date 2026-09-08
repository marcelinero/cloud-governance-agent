# Protección de la rama `main`

> **Nota:** la protección de ramas en repositorios **privados** requiere GitHub Pro.
> En repos **públicos** está disponible en el plan gratuito. Por eso estas reglas se
> aplican **después** de hacer el repositorio público.

## Política objetivo

La rama `main` debe estar protegida para que nadie (incluido el owner, salvo override
explícito) pueda hacer push directo sin revisión y sin que el CI pase.

Reglas:
- Requerir Pull Request antes de hacer merge (mínimo 1 aprobación).
- Descartar aprobaciones obsoletas cuando llegan nuevos commits.
- Requerir que el check de CI (`Lint y Tests`) pase antes del merge.
- Requerir que la rama esté actualizada con `main` antes del merge.
- Prohibir force-push y borrado de la rama.
- Aplicar las reglas también a administradores (`enforce_admins`).

## Cómo aplicarla (una vez el repo sea público)

Con GitHub CLI autenticado (`gh auth status`):

```bash
gh api -X PUT repos/marcelinero/cloud-governance-agent/branches/main/protection \
  --input .github/branch-protection.json
```

Contenido de `.github/branch-protection.json`:

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Lint y Tests"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

## Verificación

```bash
gh api repos/marcelinero/cloud-governance-agent/branches/main/protection
```
