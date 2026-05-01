"""Weather observation ORM model.

This module defines the WeatherObservation model representing a single
day's weather measurements from a weather station.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from weather_platform.models.base import BaseEntity


class WeatherObservation(BaseEntity):
    """ORM model for a single day's weather observation from a station.
    
    Each record represents the daily weather measurements (max temp, min temp,
    precipitation) for a specific weather station on a specific date.
    
    Attributes:
        station_id: NOAA station identifier (e.g., 'USC00110072')
        observation_date: Date of the observation (YYYY-MM-DD format)
        max_temp_c: Maximum temperature in Celsius, or None if missing
        min_temp_c: Minimum temperature in Celsius, or None if missing
        precipitation_cm: Precipitation in centimeters, or None if missing
        source_file: Name of the data file this observation came from
        
    Constraints:
        - Unique constraint on (station_id, observation_date) prevents duplicates
        - Indexes on (station_id, observation_date) and (observation_date) for query performance
    """
    __tablename__ = "weather_observations"
    __table_args__ = (
        # Unique constraint prevents duplicate observations for same station/date
        UniqueConstraint(
            "station_id",
            "observation_date",
            name="uq_weather_observations_station_date",
        ),
        # Index for efficient queries by station and date range
        Index("ix_weather_observations_station_date", "station_id", "observation_date"),
        # Index for efficient time-series queries across all stations
        Index("ix_weather_observations_observation_date", "observation_date"),
    )

    # NOAA station identifier
    station_id: Mapped[str] = mapped_column(String, nullable=False)
    
    # Date of the observation
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Temperature and precipitation measurements (nullable for missing data)
    # Numeric(5, 2) allows values like 99.99 (max 999.99)
    max_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    
    # Numeric(8, 2) allows larger precipitation values like 9999.99
    precipitation_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    
    # Audit field: tracks which data file this observation was ingested from
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            "WeatherObservation("
            f"station_id={self.station_id!r}, observation_date={self.observation_date!r})"
        )
