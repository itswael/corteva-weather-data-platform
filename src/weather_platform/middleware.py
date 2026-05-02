from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from weather_platform.utils.observability import (
    REQUEST_ID_HEADER,
    generate_request_id,
    get_application_metrics,
    reset_request_id,
    set_request_id,
)
from weather_platform.utils.structured_logging import log_structured_event


def install_observability_middleware(app: FastAPI) -> None:
    """Install request correlation, request metrics, and structured access logging."""

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        metrics = get_application_metrics()
        request_id = request.headers.get(REQUEST_ID_HEADER) or generate_request_id()
        token = set_request_id(request_id)
        request.state.request_id = request_id

        started_at = perf_counter()
        metrics.record_request_start()
        log_structured_event(
            "request.started",
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query),
        )

        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - defensive path
            duration_ms = (perf_counter() - started_at) * 1000
            metrics.record_request_end(status_code=500, duration_ms=duration_ms, failed=True)
            log_structured_event(
                "request.failed",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=round(duration_ms, 2),
                error_type=type(exc).__name__,
            )
            reset_request_id(token)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={REQUEST_ID_HEADER: request_id},
            )

        duration_ms = (perf_counter() - started_at) * 1000
        metrics.record_request_end(
            status_code=response.status_code,
            duration_ms=duration_ms,
            failed=response.status_code >= 500,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        log_structured_event(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        reset_request_id(token)
        return response
