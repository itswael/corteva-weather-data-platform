from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RequestMetricsRead(BaseModel):
    """Request lifecycle metrics for health endpoints."""

    total_requests: int = Field(ge=0, description="Total HTTP requests observed", example=10)
    active_requests: int = Field(ge=0, description="Requests currently in flight", example=0)
    failed_requests: int = Field(ge=0, description="Requests that ended in failure", example=1)
    average_duration_ms: float = Field(ge=0, description="Average request latency in milliseconds", example=12.5)
    max_duration_ms: float = Field(ge=0, description="Maximum observed request latency in milliseconds", example=25.0)
    status_counts: dict[str, int] = Field(
        description="Response counts grouped by HTTP status code",
        example={"200": 9, "500": 1},
    )


class IngestionMetricsRead(BaseModel):
    """Ingestion pipeline metrics for health endpoints."""

    files_processed: int = Field(ge=0, description="Successfully ingested files", example=3)
    files_failed: int = Field(ge=0, description="Files that failed parsing or ingestion", example=0)
    records_processed: int = Field(ge=0, description="Parsed observation records", example=42)
    records_inserted: int = Field(ge=0, description="Observation rows persisted via upsert", example=42)
    duplicate_records: int = Field(ge=0, description="Duplicate rows skipped by upsert semantics", example=2)
    parse_errors: int = Field(ge=0, description="Files that failed during parsing", example=0)
    last_ingestion_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent ingestion event",
        example="2026-05-01T23:50:00Z",
    )


class HealthResponseRead(BaseModel):
    """Production health response for liveness and readiness checks."""

    status: Literal["ok", "degraded"] = Field(description="Overall service health", example="ok")
    service: str = Field(description="Service name", example="weather-platform")
    version: str = Field(description="Service version", example="0.1.0")
    environment: str = Field(description="Deployment environment", example="test")
    request_id: str = Field(description="Request correlation identifier", example="d2f8d7c4a8e84f9ab0e2b9e5f3f7c8a1")
    timestamp: datetime = Field(description="Health check timestamp", example="2026-05-01T23:50:00Z")
    database_status: str | None = Field(default=None, description="Database readiness state", example="ok")
    database_error: str | None = Field(default=None, description="Database readiness error, if any", example=None)
    request_metrics: RequestMetricsRead
    ingestion_metrics: IngestionMetricsRead
