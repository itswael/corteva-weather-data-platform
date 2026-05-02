from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


@dataclass(frozen=True)
class YearlyAggregateData:
    """Result of aggregating observations for a station/year.
    
    Attributes:
        avg_max_temp_c: Average of max_temp_c values (ignoring NULLs)
        avg_min_temp_c: Average of min_temp_c values (ignoring NULLs)
        total_precipitation_cm: Sum of precipitation_cm values (ignoring NULLs)
        observation_count: Count of observations with at least one non-NULL measurement
    """
    avg_max_temp_c: Decimal | None
    avg_min_temp_c: Decimal | None
    total_precipitation_cm: Decimal | None
    observation_count: int


class WeatherRepository(Protocol):
    """Repository protocol for weather data operations.
    
    Defines contracts for observation management and aggregation queries.
    """
    
    def upsert_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        """Insert or update a weather observation."""
        ...

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        """Retrieve a specific observation by station and date."""
        ...

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        """Insert or update yearly statistics."""
        ...

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        """List all yearly statistics for a station."""
        ...
    
    def aggregate_yearly_observations(
        self, station_id: str, year: int
    ) -> YearlyAggregateData:
        """Calculate yearly aggregates from observations.
        
        Aggregates observations for a specific station and year, calculating:
        - Average max temperature (ignoring NULLs)
        - Average min temperature (ignoring NULLs)
        - Total precipitation (ignoring NULLs)
        - Observation count (records with at least one non-NULL measurement)
        
        Args:
            station_id: NOAA station identifier
            year: Calendar year
            
        Returns:
            YearlyAggregateData: Aggregated measurements
        """
        ...
    
    def query_observations(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[Sequence[WeatherObservation], int]:
        """Query observations with optional filtering and pagination.
        
        Filters observations by station_id and date range, then returns
        a page of results with the total count of matching records.
        
        Args:
            skip: Number of records to skip (pagination offset, default 0)
            limit: Maximum records to return per page (default 100)
            station_id: Filter by station identifier (optional)
            start_date: Filter observations on or after this date (optional)
            end_date: Filter observations on or before this date (optional)
            
        Returns:
            tuple[Sequence[WeatherObservation], int]: (observations, total_count)
        """
        ...
    
    def query_yearly_stats(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> tuple[Sequence[WeatherYearlyStat], int]:
        """Query yearly statistics with optional filtering and pagination.
        
        Filters yearly stats by station_id and year range, then returns
        a page of results with the total count of matching records.
        
        Args:
            skip: Number of records to skip (pagination offset, default 0)
            limit: Maximum records to return per page (default 100)
            station_id: Filter by station identifier (optional)
            start_year: Filter stats from this year onward (optional)
            end_year: Filter stats up to this year (optional)
            
        Returns:
            tuple[Sequence[WeatherYearlyStat], int]: (yearly_stats, total_count)
        """
        ...
