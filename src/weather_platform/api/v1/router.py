from fastapi import APIRouter

from weather_platform.api.v1.endpoints.health import router as health_router
from weather_platform.api.v1.endpoints.weather import router as weather_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(weather_router)
