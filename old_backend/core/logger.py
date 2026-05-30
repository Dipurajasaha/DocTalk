from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from .config import settings


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key in ("component", "request_id", "path", "method", "status_code"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_doctalk_configured", False):
        return root_logger

    root_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())
    setattr(root_logger, "_doctalk_configured", True)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
