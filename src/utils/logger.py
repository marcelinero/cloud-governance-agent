"""
logger.py — Logger estructurado JSON para el Cloud Governance Agent.

Produce logs en formato JSON compatible con CloudWatch Logs Insights,
facilitando queries y dashboards de observabilidad.

Uso:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Iniciando checker", extra={"checker": "IAMChecker", "account_id": "123"})
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """
    Formateador de logs que produce JSON estructurado en una sola línea.

    Cada registro incluye:
      - timestamp (ISO 8601 UTC)
      - level (INFO, WARNING, ERROR, etc.)
      - logger (nombre del módulo)
      - message
      - Campos extra opcionales (account_id, checker, region, etc.)
      - exc_info (si hay excepción)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }

        # Agregar campos extra (ej: account_id, checker, region, finding_id)
        reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in reserved and not key.startswith("_"):
                log_entry[key] = value

        # Incluir traceback si hay excepción
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Retorna un logger con el formateador JSON configurado.

    Args:
        name:  Nombre del logger, usualmente __name__ del módulo.
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR).
               Si no se especifica, usa la variable de entorno LOG_LEVEL
               o INFO por defecto.

    Returns:
        logging.Logger: Logger configurado con handler JSON a stdout.
    """
    log_level_str = level or os.environ.get("LOG_LEVEL", "INFO")
    log_level     = getattr(logging, log_level_str.upper(), logging.INFO)

    logger = logging.getLogger(name)

    # Evitar agregar múltiples handlers si el logger ya fue configurado
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


# Logger raíz del CGA para uso en módulos que no crean su propio logger
root_logger = get_logger("cga")
