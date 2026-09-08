# Política de Seguridad

## Reporte de vulnerabilidades

Si encuentras una vulnerabilidad de seguridad en el Cloud Governance Agent, por favor
**no la reportes en un issue público**. En su lugar, usa el reporte privado de
vulnerabilidades de GitHub:

1. Ve a la pestaña **Security** del repositorio.
2. Selecciona **Report a vulnerability**.

Nos comprometemos a revisar los reportes en un plazo razonable y a coordinar la
divulgación responsable.

## Buenas prácticas para colaboradores

Este proyecto audita cuentas AWS reales, por lo que el manejo de datos sensibles es
crítico. Al contribuir:

- **No incluyas datos reales** en código, tests, documentación o reportes de ejemplo:
  - Account IDs reales de AWS (usa el placeholder `123456789012`).
  - Nombres de personas, correos corporativos reales o identificadores de usuarios IAM reales.
  - Credenciales, access keys, tokens, contraseñas o claves privadas.
  - ARNs, endpoints o IDs de recursos de cuentas productivas.
- **No versiones configuración local sensible**, como `.kiro/settings/mcp.json`,
  archivos `.env` o credenciales de AWS. El `.gitignore` ya cubre estos casos.
- El agente opera con **permisos de solo lectura** más `s3:PutObject` y `ses:SendRawEmail`.
  Cualquier cambio que amplíe permisos debe justificarse y revisarse con cuidado.

## Alcance

Esta política aplica a la última versión publicada en la rama `main`.
