"""FastAPI application factory and entry point.

This module creates and configures the FastAPI application instance with
all necessary routes, middleware, and settings.
"""
from fastapi import FastAPI

from weather_platform.api.router import api_router
from weather_platform.config.settings import get_settings
from weather_platform.utils.logger import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Initializes the FastAPI instance with environment-appropriate settings,
    configures logging, and includes all API routers.
    
    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-grade FastAPI foundation for weather ingestion and analytics.",
    )
    app.include_router(api_router)
    return app


# Global application instance used by ASGI servers (e.g., uvicorn)
app = create_app()
