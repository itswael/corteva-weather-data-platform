"""Core weather service for observations and statistics.

Coordinates repository operations and delegates aggregation to
specialized WeatherAggregationService.
"""
from datetime import date
from collections.abc import Sequence

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository
from weather_platform.schemas.weather import (
    WeatherObservationCreate,
    WeatherObservationRead,
    WeatherYearlyStatCreate,
    WeatherYearlyStatRead,
    PaginatedWeatherObservationRead,
    PaginatedWeatherYearlyStatRead,
)


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

    def ingest_observations_batch(self, observations: list[WeatherObservationCreate], chunk_size: int = 1000) -> int:
        """Bulk ingest observations using repository bulk method. Returns number of records processed."""
        # Delegate to repository optimized bulk implementation when available
        if hasattr(self.repository, "bulk_upsert_observations"):
            return self.repository.bulk_upsert_observations(observations=observations, chunk_size=chunk_size)

        # Fallback: sequential ingestion
        count = 0
        for obs in observations:
            self.ingest_observation(obs)
            count += 1
        return count

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
    
    def query_observations(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PaginatedWeatherObservationRead:
        """Query observations with pagination and filtering.
        
        Delegates to repository for the actual query, then packages the results
        into a paginated response DTO.
        
        Args:
            skip: Number of records to skip (pagination offset)
            limit: Maximum records per page (capped at 1000)
            station_id: Optional station identifier filter
            start_date: Optional minimum observation date
            end_date: Optional maximum observation date
            
        Returns:
            PaginatedWeatherObservationRead: Paginated observations with total count
        """
        # Cap limit to prevent excessive data transfers
        safe_limit = min(limit, 1000)
        
        observations, total_count = self.repository.query_observations(
            skip=skip,
            limit=safe_limit,
            station_id=station_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        return PaginatedWeatherObservationRead(
            items=[WeatherObservationRead.model_validate(obs) for obs in observations],
            total=total_count,
            skip=skip,
            limit=safe_limit,
        )
    
    def query_yearly_stats(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> PaginatedWeatherYearlyStatRead:
        """Query yearly statistics with pagination and filtering.
        
        Delegates to repository for the actual query, then packages the results
        into a paginated response DTO with version-safe contracts.
        
        Args:
            skip: Number of records to skip (pagination offset)
            limit: Maximum records per page (capped at 1000)
            station_id: Optional station identifier filter
            start_year: Optional minimum year (inclusive)
            end_year: Optional maximum year (inclusive)
            
        Returns:
            PaginatedWeatherYearlyStatRead: Paginated yearly stats with total count
        """
        # Cap limit to prevent excessive data transfers
        safe_limit = min(limit, 1000)
        
        yearly_stats, total_count = self.repository.query_yearly_stats(
            skip=skip,
            limit=safe_limit,
            station_id=station_id,
            start_year=start_year,
            end_year=end_year,
        )
        
        return PaginatedWeatherYearlyStatRead(
            items=[WeatherYearlyStatRead.model_validate(stat) for stat in yearly_stats],
            total=total_count,
            skip=skip,
            limit=safe_limit,
        )
