from fastapi import FastAPI

from weather_platform.api.router import api_router
from weather_platform.config.settings import get_settings
from weather_platform.utils.logger import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-grade FastAPI foundation for weather ingestion and analytics.",
    )
    app.include_router(api_router)
    return app


app = create_app()
