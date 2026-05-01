"""API router aggregation and versioning.

This module serves as the root router that includes all API versions.
Implements API versioning through URL prefixes (e.g., /api/v1/, /api/v2/).

Current API Structure:
- /api/v1/: Version 1 endpoints (health checks, weather observations)

Router Hierarchy:
api_router (root)
  └─ /api
      └─ api_v1_router (prefix=/api)
          ├─ /health: Health check endpoint
          └─ /weather: Weather data endpoints
"""
from fastapi import APIRouter

from weather_platform.api.v1.router import api_v1_router

# Root API router aggregating all API versions
api_router = APIRouter()

# Include v1 API routes under /api/v1 prefix
api_router.include_router(api_v1_router, prefix="/api")
