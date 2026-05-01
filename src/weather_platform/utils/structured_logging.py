from __future__ import annotations

import json
import logging
from typing import Any


def log_structured_event(event_name: str, **fields: Any) -> None:
    payload = {"event": event_name, **fields}
    logging.getLogger("weather_platform.ingestion").info(json.dumps(payload, sort_keys=True))
