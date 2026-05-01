from fastapi import APIRouter

from weather_platform.api.v1.router import api_v1_router

api_router = APIRouter()
api_router.include_router(api_v1_router, prefix="/api")
