"""Pydantic schemas for weather data API and database serialization.

This module defines DTOs (Data Transfer Objects) for API requests/responses
and database creation. Schemas provide validation, documentation, and type safety.
"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WeatherObservationCreate(BaseModel):
    """Schema for creating a weather observation record.
    
    Used for:
    - API POST requests
    - Database inserts/updates
    - File ingestion workflows
    
    Attributes:
        station_id: NOAA station identifier (required, non-empty)
        observation_date: Date of observation
        max_temp_c: Maximum temperature in Celsius (nullable)
        min_temp_c: Minimum temperature in Celsius (nullable)
        precipitation_cm: Precipitation in centimeters (nullable)
        source_file: Data file this observation came from (audit field, optional)
    """
    station_id: str = Field(min_length=1)
    observation_date: date
    max_temp_c: Decimal | None = None
    min_temp_c: Decimal | None = None
    precipitation_cm: Decimal | None = None
    source_file: str | None = None


class WeatherObservationRead(WeatherObservationCreate):
    """Schema for reading a weather observation from the database.
    
    Extends WeatherObservationCreate with database-generated fields:
    - id: Primary key
    - created_at: Timestamp when record was created
    
    Used for API GET responses and ORM deserialization.
    """
    id: int
    created_at: datetime

    # Allow reading from ORM attributes (use_attributes_for_readinferring=True equivalent)
    model_config = ConfigDict(from_attributes=True)


class WeatherYearlyStatCreate(BaseModel):
    """Schema for creating yearly weather statistics.
    
    Used for:
    - API POST requests for aggregated statistics
    - Database inserts/updates of yearly summaries
    
    Attributes:
        station_id: NOAA station identifier (required, non-empty)
        year: Calendar year for statistics (1800-3000 range for validation)
        avg_max_temp_c: Average daily maximum temperature (nullable)
        avg_min_temp_c: Average daily minimum temperature (nullable)
        total_precipitation_cm: Sum of daily precipitation (nullable)
        observation_count: Number of daily observations included (non-negative)
    """
    station_id: str = Field(min_length=1)
    year: int = Field(ge=1800, le=3000)
    avg_max_temp_c: Decimal | None = None
    avg_min_temp_c: Decimal | None = None
    total_precipitation_cm: Decimal | None = None
    observation_count: int = Field(ge=0)


class WeatherYearlyStatRead(WeatherYearlyStatCreate):
    """Schema for reading yearly statistics from the database.
    
    Extends WeatherYearlyStatCreate with database-generated fields:
    - id: Primary key
    - created_at: Timestamp when record was created
    
    Used for API GET responses and ORM deserialization.
    """
    id: int
    created_at: datetime

    # Allow reading from ORM attributes
    model_config = ConfigDict(from_attributes=True)
