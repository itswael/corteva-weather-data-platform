"""Health check endpoint for liveness/readiness probes.

Provides basic health status information useful for Kubernetes liveness
probes, load balancer health checks, and API monitoring.
"""
from fastapi import APIRouter

from weather_platform.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Perform a basic health check of the API.
    
    Returns application metadata indicating the service is alive and responsive.
    Called by load balancers and container orchestration platforms to verify
    service health.
    
    Returns:
        dict[str, str]: Health status with application info:
            - status: "ok" if service is healthy
            - app: Application name from settings
            - version: Application version from settings
            
    Example Response:
        {
            "status": "ok",
            "app": "weather-platform",
            "version": "0.1.0"
        }
    """
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
