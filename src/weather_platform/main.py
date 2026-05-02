from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from weather_platform.api.router import api_router
from weather_platform.config.settings import get_settings
from weather_platform.middleware import install_observability_middleware
from weather_platform.utils.observability import get_application_metrics
from weather_platform.utils.logger import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-grade FastAPI foundation for weather ingestion and analytics.",
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )

    if settings.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    if settings.enforce_https:
        app.add_middleware(HTTPSRedirectMiddleware)

    app.state.metrics = get_application_metrics()
    install_observability_middleware(app)
    app.include_router(api_router)
    return app


app = create_app()
