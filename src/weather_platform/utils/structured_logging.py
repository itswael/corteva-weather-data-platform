"""Structured logging utilities for JSON-formatted events.

This module provides helpers for emitting structured JSON logs suitable
for log aggregation systems (ELK, Splunk, CloudWatch, etc.).
"""
from __future__ import annotations

import json
import logging
from typing import Any


def log_structured_event(event_name: str, **fields: Any) -> None:
    """Emit a structured JSON log event.
    
    Combines the event name with additional fields into a JSON object and
    logs it. Useful for integration with log aggregation and monitoring systems.
    
    Args:
        event_name: Name of the event (e.g., "weather_file_ingestion_started")
        **fields: Additional fields to include in the log (e.g., file_path, error, duration_ms)
        
    Example:
        log_structured_event(
            "weather_file_ingestion_completed",
            source_file="USC00110072.txt",
            processed=365,
            inserted=365,
            skipped_duplicates=0,
            duration_ms=342,
            status="success"
        )
        
        Produces JSON:
        {
            "event": "weather_file_ingestion_completed",
            "duration_ms": 342,
            "inserted": 365,
            "processed": 365,
            "skipped_duplicates": 0,
            "source_file": "USC00110072.txt",
            "status": "success"
        }
    """
    # Combine event name with fields
    payload = {"event": event_name, **fields}
    
    # Emit as JSON string to logger
    # Uses weather_platform.ingestion logger for convenient filtering/scoping
    logging.getLogger("weather_platform.ingestion").info(json.dumps(payload, sort_keys=True))
