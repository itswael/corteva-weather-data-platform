from __future__ import annotations

import logging

from weather_platform.utils.observability import get_request_id

_logger = logging.getLogger(__name__)


def log_structured_event(event: str, **fields: object) -> None:
    payload = {"event": event, "request_id": get_request_id(), **fields}
    _logger.info(payload)
