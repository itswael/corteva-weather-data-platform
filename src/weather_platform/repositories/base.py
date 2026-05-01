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
