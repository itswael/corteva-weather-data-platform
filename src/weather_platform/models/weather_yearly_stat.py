"""Weather yearly statistics ORM model.

This module defines the WeatherYearlyStat model representing aggregated
annual weather statistics for a weather station.
"""
from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from weather_platform.models.base import BaseEntity


class WeatherYearlyStat(BaseEntity):
    """ORM model for aggregated annual weather statistics from a station.
    
    Each record represents aggregated statistics (averages and totals) for
    all observations from a specific weather station during a specific year.
    
    Attributes:
        station_id: NOAA station identifier (e.g., 'USC00110072')
        year: The calendar year for these statistics
        avg_max_temp_c: Average of daily maximum temperatures in Celsius, or None if no data
        avg_min_temp_c: Average of daily minimum temperatures in Celsius, or None if no data
        total_precipitation_cm: Sum of daily precipitation in centimeters, or None if no data
        observation_count: Number of daily observations included in aggregation
        
    Constraints:
        - Unique constraint on (station_id, year) prevents duplicate annual statistics
    """
    __tablename__ = "weather_yearly_stats"
    __table_args__ = (
        # Unique constraint prevents duplicate yearly stats for same station/year
        UniqueConstraint(
            "station_id",
            "year",
            name="uq_weather_yearly_stats_station_year",
        ),
    )

    # NOAA station identifier
    station_id: Mapped[str] = mapped_column(String, nullable=False)
    
    # Calendar year for these statistics
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Aggregated temperature statistics (averages)
    # Numeric(5, 2) allows values like 99.99 (max 999.99)
    avg_max_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    avg_min_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    
    # Aggregated precipitation (total/sum), nullable if no precipitation data
    # Numeric(10, 2) allows large totals like 9999.99
    total_precipitation_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Number of daily observations included (helps validate aggregation)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"WeatherYearlyStat(station_id={self.station_id!r}, year={self.year!r})"
