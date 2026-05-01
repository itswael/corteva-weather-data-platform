"""Version 1 API route aggregation.

Assembles all v1 endpoints (health, weather, etc.) under the /v1 prefix.
This module serves as the entry point for all v1 API functionality.

Router Hierarchy:
api_v1_router (prefix=/v1)
├─ health_router: GET /v1/health
└─ weather_router: 
    ├─ POST /v1/weather/observations
    ├─ GET /v1/weather/observations/{station_id}/{observation_date}
    ├─ POST /v1/weather/yearly-stats
    └─ GET /v1/weather/yearly-stats/{station_id}

When included in the root api_router with prefix=/api:
- Health: GET /api/v1/health
- Weather: POST /api/v1/weather/observations
- etc.
"""
from fastapi import APIRouter

from weather_platform.api.v1.endpoints.health import router as health_router
from weather_platform.api.v1.endpoints.weather import router as weather_router

# Root router for v1 API
api_v1_router = APIRouter(prefix="/v1")

# Include endpoint routers
# Health check endpoints
api_v1_router.include_router(health_router)

# Weather data endpoints (observations and yearly statistics)
api_v1_router.include_router(weather_router)
