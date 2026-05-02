from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaginatedWeatherObservationRead(BaseModel):
    """Paginated response for weather observations.
    
    Attributes:
        items: List of observation records for the current page
        total: Total count of observations matching the filter criteria
        skip: Number of records skipped (pagination offset)
        limit: Maximum records per page
    """
    items: list["WeatherObservationRead"]
    total: int
    skip: int
    limit: int


class PaginatedWeatherYearlyStatRead(BaseModel):
    """Paginated response for yearly weather statistics.
    
    Version-safe response contract for querying aggregated yearly stats.
    Includes pagination metadata and timestamps for operational visibility.
    
    Attributes:
        items: List of yearly stat records for the current page
        total: Total count of stats matching the filter criteria
        skip: Number of records skipped (pagination offset)
        limit: Maximum records per page
    """
    items: list[WeatherYearlyStatRead]
    total: int
    skip: int
    limit: int


class WeatherObservationCreate(BaseModel):
    station_id: str = Field(min_length=1)
    observation_date: date
    max_temp_c: Decimal | None = None
    min_temp_c: Decimal | None = None
    precipitation_cm: Decimal | None = None
    source_file: str | None = None


class WeatherObservationRead(WeatherObservationCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeatherYearlyStatCreate(BaseModel):
    station_id: str = Field(min_length=1)
    year: int = Field(ge=1800, le=3000)
    avg_max_temp_c: Decimal | None = None
    avg_min_temp_c: Decimal | None = None
    total_precipitation_cm: Decimal | None = None
    observation_count: int = Field(ge=0)


class WeatherYearlyStatRead(WeatherYearlyStatCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
