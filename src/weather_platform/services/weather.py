"""Core weather service for observations and statistics.

Coordinates repository operations and delegates aggregation to
specialized WeatherAggregationService.
"""
from datetime import date
from collections.abc import Sequence

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class WeatherService:
    """Service coordinating weather observation and statistic operations.
    
    Handles CRUD operations for observations and provides access to
    yearly statistics. Delegates aggregation calculations to
    WeatherAggregationService.
    
    Attributes:
        repository: Weather data repository for persistence
    """
    
    def __init__(self, repository: WeatherRepository) -> None:
        """Initialize service with repository.
        
        Args:
            repository: WeatherRepository implementation
        """
        self.repository = repository

    def ingest_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        """Insert or update a weather observation.
        
        Args:
            observation: Observation data to persist
            
        Returns:
            WeatherObservation: Stored observation with id and metadata
        """
        return self.repository.upsert_observation(observation)

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        """Retrieve a specific observation.
        
        Args:
            station_id: NOAA station identifier
            observation_date: Date of observation
            
        Returns:
            WeatherObservation | None: Observation if found, None otherwise
        """
        return self.repository.get_observation(station_id, observation_date)

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        """Insert or update yearly statistics.
        
        Args:
            stat: Yearly statistic data
            
        Returns:
            WeatherYearlyStat: Stored statistics with id and metadata
        """
        return self.repository.upsert_yearly_stat(stat)

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        """List all yearly statistics for a station.
        
        Args:
            station_id: NOAA station identifier
            
        Returns:
            Sequence[WeatherYearlyStat]: Statistics ordered by year ascending
        """
        return self.repository.list_yearly_stats(station_id)
