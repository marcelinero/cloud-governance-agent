# Requisitos — Cloud Governance Agent (CGA)

## 1. Requisitos Funcionales

### RF-01: Auditoría de Seguridad y Cumplimiento

#### RF-01.1 IAM
- El agente DEBE detectar usuarios IAM sin MFA habilitado
- El agente DEBE detectar access keys con más de 90 días sin rotación
- El agente DEBE detectar usuarios IAM sin actividad en los últimos 90 días
- El agente DEBE detectar políticas IAM con permisos de administrador completo (`*:*`) adjuntas directamente a usuarios

#### RF-01.2 Red y Perímetro
- El agente DEBE detectar Security Groups con puertos críticos abiertos al mundo (0.0.0.0/0): SSH (22), RDP (3389), base de datos (3306, 5432, 1433, 27017)
- El agente DEBE detectar buckets S3 con acceso público habilitado
- El agente DEBE detectar distribuciones CloudFront sin WAF asociado
- El agente DEBE detectar instancias RDS con acceso público habilitado
- El agente DEBE detectar VPCs sin Flow Logs activos

#### RF-01.3 Trazabilidad y Logging
- El agente DEBE verificar que CloudTrail esté habilitado y activo en todas las regiones
- El agente DEBE detectar buckets S3 sin server access logging habilitado
- El agente DEBE detectar funciones Lambda sin configuración de log group en CloudWatch

#### RF-01.4 Etiquetado (Tagging)
- El agente DEBE detectar recursos sin las etiquetas obligatorias: `Owner`, `Project`, `Environment`, `CostCenter`
- Los servicios a verificar son: EC2, RDS, S3, Lambda, ECS, DynamoDB, CloudFront

---

### RF-02: Optimización de Costos (FinOps)

#### RF-02.1 Cómputo
- El agente DEBE detectar instancias EC2 con CPU promedio menor al 10% durante los últimos 7 días
- El agente DEBE detectar instancias EC2 en estado `stopped` por más de 7 días consecutivos
- El agente DEBE detectar funciones Lambda sin invocaciones en los últimos 30 días
- El agente DEBE detectar servicios ECS/Fargate con utilización de CPU/memoria menor al 20% en los últimos 7 días

#### RF-02.2 Almacenamiento
- El agente DEBE detectar buckets S3 sin política de ciclo de vida (lifecycle policy) configurada
- El agente DEBE detectar snapshots EBS con más de 30 días sin estar adjuntos a ninguna instancia
- El agente DEBE detectar AMIs no utilizadas con más de 90 días de antigüedad
- El agente DEBE detectar volúmenes EBS en estado `available` (no adjuntos) por más de 7 días

#### RF-02.3 Red
- El agente DEBE detectar Elastic IPs no asociadas a ningún recurso
- El agente DEBE detectar NAT Gateways sin tráfico en los últimos 7 días
- El agente DEBE detectar Load Balancers (ALB/NLB) sin tráfico en los últimos 7 días

#### RF-02.4 Base de Datos
- El agente DEBE detectar instancias RDS con CPU promedio menor al 10% en los últimos 7 días
- El agente DEBE detectar instancias RDS en estado `stopped` por más de 7 días
- El agente DEBE detectar tablas DynamoDB con menos de 10 operaciones de lectura/escritura por día en los últimos 7 días

#### RF-02.5 Estimación de Ahorro
- El agente DEBE calcular el costo mensual estimado de cada recurso identificado como candidato a optimización usando AWS Cost Explorer API
- El agente DEBE calcular el ahorro potencial total consolidado por área/equipo

---

### RF-03: Reportes y Notificaciones

#### RF-03.1 Generación de Reporte
- El agente DEBE generar un reporte en formato HTML con los hallazgos organizados por dominio (Seguridad, FinOps, Cumplimiento)
- Cada hallazgo DEBE incluir: recurso afectado, región, nivel de severidad (Critical/High/Medium/Low), descripción del problema, recomendación de acción y costo estimado si aplica
- El reporte DEBE incluir un resumen ejecutivo con totales por severidad y ahorro potencial estimado
- El reporte HTML DEBE ser adjuntado al email y también almacenado como archivo JSON en S3

#### RF-03.2 Notificaciones por Rol
- El agente DEBE enviar el reporte completo al equipo de Auditoría
- El agente DEBE enviar hallazgos de FinOps (costos) al equipo FinOps
- El agente DEBE enviar hallazgos de Seguridad al equipo de Riesgos/Seguridad
- El agente DEBE notificar al dueño del recurso (tag `Owner`) con los hallazgos específicos de sus recursos
- Las notificaciones DEBEN enviarse vía Amazon SES

#### RF-03.3 Almacenamiento de Evidencias
- El agente DEBE almacenar cada reporte en S3 en formato JSON y HTML con la estructura:
  `s3://cga-reports-{account-id}/YYYY/MM/DD/cga-report-{fecha}_{hora}-{id}.{json,html}`
  (el nombre incluye fecha y hora de ejecución UTC para trazabilidad e identificación)
- Los reportes DEBEN ser retenidos por 365 días mediante lifecycle policy

---

### RF-04: Ejecución

#### RF-04.1 Ejecución Bajo Demanda
- El agente DEBE poder ejecutarse manualmente invocando la función Lambda directamente desde consola, CLI o Kiro

#### RF-04.2 Ejecución Programada
- El agente DEBE ejecutarse automáticamente todos los lunes a las 08:00 AM (hora configurada en variable de entorno)
- La programación DEBE gestionarse mediante Amazon EventBridge Scheduler

---

## 2. Requisitos No Funcionales

### RNF-01: Seguridad
- Las credenciales y configuraciones sensibles DEBEN almacenarse en AWS Secrets Manager o SSM Parameter Store, nunca en código
- El rol IAM de la Lambda DEBE seguir el principio de mínimo privilegio
- Los reportes en S3 DEBEN estar cifrados con SSE-S3

### RNF-02: Rendimiento
- La ejecución completa del agente DEBE completarse en menos de 15 minutos
- El timeout de la función Lambda DEBE configurarse en 900 segundos (15 minutos)

### RNF-03: Observabilidad
- La Lambda DEBE registrar logs estructurados (JSON) en CloudWatch Logs
- DEBE existir una alarma en CloudWatch que notifique si la ejecución falla

### RNF-04: Portabilidad
- El proyecto DEBE poder desplegarse en cualquier cuenta y región AWS con mínima configuración
- Todos los parámetros de configuración (emails, región, umbrales) DEBEN ser configurables vía variables de entorno o CDK context

### RNF-05: Mantenibilidad
- El código DEBE seguir PEP 8
- Cada checker de auditoría DEBE ser un módulo Python independiente para facilitar extensión
- El proyecto DEBE incluir README completo con instrucciones de despliegue

---

## 3. Restricciones

- Lenguaje: Python 3.12
- IaC: AWS CDK v2 con Python
- Región por defecto: us-east-1 (configurable)
- El agente audita la cuenta AWS donde está desplegado
- Se requiere que Amazon SES tenga verificados los emails de destino (sandbox mode) o estar fuera de sandbox para producción
