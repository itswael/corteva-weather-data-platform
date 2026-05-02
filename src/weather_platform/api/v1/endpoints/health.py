from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from weather_platform.config.settings import get_settings
from weather_platform.config.database import get_db_session
from weather_platform.schemas.health import HealthResponseRead, IngestionMetricsRead, RequestMetricsRead
from weather_platform.utils.observability import get_request_id
from weather_platform.utils.structured_logging import log_structured_event

router = APIRouter(tags=["health"])


def _build_health_response(request: Request, *, status_value: str, database_status: str | None = None, database_error: str | None = None) -> HealthResponseRead:
    settings = get_settings()
    metrics_snapshot = request.app.state.metrics.snapshot()
    return HealthResponseRead(
        status=status_value,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        request_id=getattr(request.state, "request_id", None) or get_request_id() or "",
        timestamp=datetime.now(timezone.utc),
        database_status=database_status,
        database_error=database_error,
        request_metrics=RequestMetricsRead.model_validate(metrics_snapshot["request"]),
        ingestion_metrics=IngestionMetricsRead.model_validate(metrics_snapshot["ingestion"]),
    )


@router.get("/health", response_model=HealthResponseRead)
def health_check(request: Request) -> HealthResponseRead:
    """Return application health details for liveness monitoring."""
    response = _build_health_response(request, status_value="ok")
    log_structured_event("health.check", mode="live", status=response.status)
    return response


@router.get("/health/live", response_model=HealthResponseRead)
def health_live(request: Request) -> HealthResponseRead:
    """Return liveness status without touching downstream dependencies."""
    response = _build_health_response(request, status_value="ok")
    log_structured_event("health.check", mode="live", status=response.status)
    return response


@router.get("/health/ready", response_model=HealthResponseRead, responses={503: {"model": HealthResponseRead}})
def health_ready(request: Request, db_session=Depends(get_db_session)) -> HealthResponseRead:
    """Return readiness status including a database connectivity check."""
    try:
        db_session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive path
        response = _build_health_response(
            request,
            status_value="degraded",
            database_status="down",
            database_error=type(exc).__name__,
        )
        log_structured_event("health.check", mode="ready", status=response.status, database_status="down")
        return response

    response = _build_health_response(request, status_value="ok", database_status="ok")
    log_structured_event("health.check", mode="ready", status=response.status, database_status="ok")
    return response
