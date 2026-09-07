# Diagrama de Flujo de Ejecución — Cloud Governance Agent (CGA)

## Versión: 1.0.0 | Fecha: 2026-09-07

---

## Flujo Completo de Ejecución

```mermaid
flowchart TD
    A([🕐 EventBridge\nLunes 08:00 AM]) --> C
    B([👤 Invocación Manual\nCLI / Consola / Kiro]) --> C

    C[Lambda Handler\nInicia ejecución] --> D[Carga configuración\ndesde variables de entorno]
    D --> E[Inicializa logger JSON\ny clientes boto3]

    E --> F{ThreadPoolExecutor\n3 workers en paralelo}

    F --> G[Security Checker]
    F --> H[FinOps Checker]
    F --> I[Compliance Checker]

    G --> G1[IAM Checker]
    G --> G2[S3 Security Checker]
    G --> G3[Network Checker]
    G --> G4[RDS Security Checker]
    G --> G5[CloudFront Checker]
    G --> G6[Logging Checker]

    H --> H1[EC2 FinOps Checker]
    H --> H2[RDS FinOps Checker]
    H --> H3[Lambda Checker]
    H --> H4[Storage Checker]
    H --> H5[Network FinOps Checker]
    H --> H6[DynamoDB Checker]

    I --> I1[Tagging Checker]

    G1 & G2 & G3 & G4 & G5 & G6 --> J
    H1 & H2 & H3 & H4 & H5 & H6 --> J
    I1 --> J

    J[Aggregator\nConsolida findings] --> K[Deduplica por\nresource_id + category]
    K --> L[Ordena por severidad\nCritical → High → Medium → Low]
    L --> M[Calcula ReportSummary\ntotales y ahorro estimado]

    M --> N[Report Generator]
    N --> O[Genera report.json\ncon evidencias completas]
    N --> P[Genera report.html\ncon estilos inline]

    O --> Q[Upload S3 JSON + HTML\ncga-reports/YYYY/MM/DD/cga-report-FECHA_HORA-id.json y .html]

    P --> R[Notifier\nEnruta por rol]

    R --> S[Email Auditoría\nReporte completo HTML]
    R --> T[Email FinOps\nSolo hallazgos de costos]
    R --> U[Email Seguridad\nSolo hallazgos de seguridad]
    R --> V{Owner tag\nes email válido?}
    V -->|Sí| W[Email Owner\nHallazgos de sus recursos]
    V -->|No| X[Skip notificación\nOwner — registra en log]

    S & T & U & W & X --> Y[Registra métricas\nen CloudWatch]
    Q --> Y

    Y --> Z[Retorna resumen JSON\ntotal_findings, critical,\nsaving_usd, duration_s]

    Z --> AA([✅ Ejecución exitosa])

    style A fill:#FF9900,color:#fff
    style B fill:#FF9900,color:#fff
    style AA fill:#2ecc71,color:#fff
    style F fill:#3498db,color:#fff
    style J fill:#9b59b6,color:#fff
    style N fill:#9b59b6,color:#fff
    style R fill:#9b59b6,color:#fff
```

---

## Flujo de Manejo de Errores

```mermaid
flowchart TD
    A[Lambda inicia] --> B{Checker falla?}
    B -->|Sí — error en checker individual| C[Registra error en CloudWatch\nContinúa con otros checkers]
    B -->|No| D[Continúa flujo normal]
    C --> D

    D --> E{Error crítico\nen Aggregator/Report?}
    E -->|Sí| F[Registra excepción completa\nen CloudWatch Logs]
    F --> G[CloudWatch Alarm\nCGA-Lambda-Errors se activa]
    G --> H[SNS notifica\nal equipo de operaciones]
    H --> I([❌ Ejecución fallida\ncon trazabilidad completa])

    E -->|No| J([✅ Ejecución exitosa])

    style I fill:#e74c3c,color:#fff
    style J fill:#2ecc71,color:#fff
    style G fill:#e74c3c,color:#fff
```

---

## Flujo de Enrutamiento de Notificaciones

```mermaid
flowchart LR
    A[Lista de Findings\nagregados] --> B[Notifier]

    B --> C[Filtra todos los findings]
    B --> D[Filtra domain == finops]
    B --> E[Filtra domain == security]
    B --> F[Agrupa por tag Owner]

    C -->|HTML completo| G[📧 audit@empresa.com\nAuditoría TI]
    D -->|HTML costos + ahorro estimado| H[📧 finops@empresa.com\nEquipo FinOps]
    E -->|HTML seguridad priorizado| I[📧 security@empresa.com\nEquipo Seguridad/Riesgos]
    F -->|HTML recursos propios| J[📧 owner@empresa.com\nDueño del Recurso]

    style G fill:#3498db,color:#fff
    style H fill:#2ecc71,color:#fff
    style I fill:#e74c3c,color:#fff
    style J fill:#FF9900,color:#fff
```

---

## Notas de Implementación

- Los tres grupos de checkers (Security, FinOps, Compliance) se ejecutan en paralelo usando `ThreadPoolExecutor(max_workers=3)`
- Si un checker individual falla, el error se registra y la ejecución continúa con los demás — **no hay falla total por error parcial**
- El `report_id` es un UUID v4 generado al inicio de cada ejecución, usado para trazabilidad en S3 y CloudWatch
- La duración total se registra en CloudWatch como métrica `CGA/ExecutionDurationSeconds`
