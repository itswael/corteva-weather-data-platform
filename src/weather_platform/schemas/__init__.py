"""Pydantic schemas for the Weather Platform."""

from weather_platform.schemas.health import (
    HealthResponseRead,
    IngestionMetricsRead,
    RequestMetricsRead,
)
from weather_platform.schemas.weather import (
    WeatherObservationCreate,
    WeatherObservationRead,
    WeatherYearlyStatCreate,
    WeatherYearlyStatRead,
)

__all__ = [
    "WeatherObservationCreate",
    "WeatherObservationRead",
    "WeatherYearlyStatCreate",
    "WeatherYearlyStatRead",
    "HealthResponseRead",
    "IngestionMetricsRead",
    "RequestMetricsRead",
]
