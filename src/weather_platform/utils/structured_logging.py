from __future__ import annotations

import json
import logging


_logger = logging.getLogger(__name__)


def log_structured_event(event: str, **fields: object) -> None:
    payload = {"event": event, **fields}
    _logger.info(json.dumps(payload, default=str))
