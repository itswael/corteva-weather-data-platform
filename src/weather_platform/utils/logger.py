from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from weather_platform.utils.observability import get_request_id


class StructuredJSONFormatter(logging.Formatter):
    """Format log records as compact JSON for production and tests."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", None) or get_request_id(),
        }
        if isinstance(record.msg, dict):
            payload.update(record.msg)
        else:
            payload["message"] = record.getMessage()
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(handler)
    # Also write structured logs to a file for local debugging/inspection
    try:
        from pathlib import Path

        logs_dir = Path.cwd() / "logs"
        logs_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / "api.log", encoding="utf-8")
        file_handler.setFormatter(StructuredJSONFormatter())
        root_logger.addHandler(file_handler)
    except Exception:
        # best-effort: do not fail application if file logging cannot be established
        pass
