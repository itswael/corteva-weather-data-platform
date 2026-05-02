from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


REQUEST_ID_HEADER = "X-Request-ID"
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    """Generate a stable request correlation identifier."""
    return uuid4().hex


def get_request_id() -> str | None:
    """Return the current request correlation identifier, if any."""
    return request_id_context.get()


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind a request correlation identifier to the current context."""
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request correlation identifier."""
    request_id_context.reset(token)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RequestMetricsSnapshot:
    total_requests: int = 0
    active_requests: int = 0
    failed_requests: int = 0
    average_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    status_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class IngestionMetricsSnapshot:
    files_processed: int = 0
    files_failed: int = 0
    records_processed: int = 0
    records_inserted: int = 0
    duplicate_records: int = 0
    parse_errors: int = 0
    last_ingestion_at: datetime | None = None


@dataclass(slots=True)
class ApplicationMetrics:
    _lock: Lock = field(default_factory=Lock, repr=False)
    _request_total: int = 0
    _request_active: int = 0
    _request_failed: int = 0
    _request_duration_total_ms: float = 0.0
    _request_duration_max_ms: float = 0.0
    _request_status_counts: dict[str, int] = field(default_factory=dict, repr=False)
    _ingestion: IngestionMetricsSnapshot = field(default_factory=IngestionMetricsSnapshot)

    def reset(self) -> None:
        """Reset all counters to a clean baseline for tests and startup."""
        with self._lock:
            self._request_total = 0
            self._request_active = 0
            self._request_failed = 0
            self._request_duration_total_ms = 0.0
            self._request_duration_max_ms = 0.0
            self._request_status_counts.clear()
            self._ingestion = IngestionMetricsSnapshot()

    def record_request_start(self) -> None:
        with self._lock:
            self._request_total += 1
            self._request_active += 1

    def record_request_end(self, status_code: int, duration_ms: float, failed: bool = False) -> None:
        with self._lock:
            self._request_active = max(0, self._request_active - 1)
            self._request_duration_total_ms += duration_ms
            self._request_duration_max_ms = max(self._request_duration_max_ms, duration_ms)
            self._request_status_counts[str(status_code)] = self._request_status_counts.get(str(status_code), 0) + 1
            if failed or status_code >= 500:
                self._request_failed += 1

    def record_ingestion(
        self,
        *,
        files_processed: int = 0,
        files_failed: int = 0,
        records_processed: int = 0,
        records_inserted: int = 0,
        duplicate_records: int = 0,
        parse_errors: int = 0,
    ) -> None:
        with self._lock:
            self._ingestion.files_processed += files_processed
            self._ingestion.files_failed += files_failed
            self._ingestion.records_processed += records_processed
            self._ingestion.records_inserted += records_inserted
            self._ingestion.duplicate_records += duplicate_records
            self._ingestion.parse_errors += parse_errors
            if files_processed > 0 or records_processed > 0 or records_inserted > 0:
                self._ingestion.last_ingestion_at = _utcnow()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            average_duration_ms = (
                self._request_duration_total_ms / self._request_total if self._request_total else 0.0
            )
            return {
                "request": asdict(RequestMetricsSnapshot(
                    total_requests=self._request_total,
                    active_requests=self._request_active,
                    failed_requests=self._request_failed,
                    average_duration_ms=round(average_duration_ms, 2),
                    max_duration_ms=round(self._request_duration_max_ms, 2),
                    status_counts=dict(self._request_status_counts),
                )),
                "ingestion": asdict(IngestionMetricsSnapshot(
                    files_processed=self._ingestion.files_processed,
                    files_failed=self._ingestion.files_failed,
                    records_processed=self._ingestion.records_processed,
                    records_inserted=self._ingestion.records_inserted,
                    duplicate_records=self._ingestion.duplicate_records,
                    parse_errors=self._ingestion.parse_errors,
                    last_ingestion_at=self._ingestion.last_ingestion_at,
                )),
            }


_APPLICATION_METRICS = ApplicationMetrics()


def get_application_metrics() -> ApplicationMetrics:
    """Return the singleton application metrics registry."""
    return _APPLICATION_METRICS
