"""Weather data service layer.

This module implements the service layer responsible for business logic
around weather observations and statistics. Services coordinate between
the API layer and the repository (data access) layer.
"""
from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from collections.abc import Sequence
from collections.abc import Iterable
from time import perf_counter

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    """Summary statistics for a batch ingestion operation.
    
    Attributes:
        processed: Total number of records processed
        inserted: Number of new records inserted
        skipped_duplicates: Number of records skipped due to duplicate key
        duration_ms: Total operation time in milliseconds
        
    This frozen dataclass is returned by batch ingestion methods to provide
    metrics for monitoring and logging.
    """
    processed: int
    inserted: int
    skipped_duplicates: int
    duration_ms: int


class WeatherService:
    """Service layer for weather observation management.
    
    Provides business logic for ingesting, retrieving, and aggregating
    weather observations. Coordinates with the repository layer for
    data persistence.
    
    Attributes:
        repository: WeatherRepository instance for data access
    """
    
    def __init__(self, repository: WeatherRepository) -> None:
        """Initialize the service with a repository.
        
        Args:
            repository: Repository instance implementing WeatherRepository protocol.
                       Allows different implementations (SQL, NoSQL, etc.)
        """
        self.repository = repository

    def ingest_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        """Ingest a single weather observation (upsert).
        
        Args:
            observation: WeatherObservationCreate schema with observation data
            
        Returns:
            WeatherObservation: The inserted or updated ORM model instance
        """
        return self.repository.upsert_observation(observation)

    def ingest_observations(self, observations: Iterable[WeatherObservationCreate]) -> IngestionSummary:
        """Ingest multiple weather observations with duplicate detection.
        
        Iterates through observations and attempts to insert each one, tracking
        statistics for successful inserts vs. duplicates. Uses idempotent
        insertion (ON CONFLICT DO NOTHING) to safely handle re-runs.
        
        Args:
            observations: Iterable of WeatherObservationCreate schemas
            
        Returns:
            IngestionSummary: Metrics about processed/inserted/skipped records
                and operation duration
        """
        started_at = perf_counter()
        processed = 0
        inserted = 0

        # Process each observation, tracking success/duplicate metrics
        for observation in observations:
            processed += 1
            # insert_observation_if_missing returns True only on new insert
            if self.repository.insert_observation_if_missing(observation):
                inserted += 1

        # Calculate derived metrics
        skipped_duplicates = processed - inserted
        duration_ms = int((perf_counter() - started_at) * 1000)
        summary = IngestionSummary(
            processed=processed,
            inserted=inserted,
            skipped_duplicates=skipped_duplicates,
            duration_ms=duration_ms,
        )
        return summary

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        """Retrieve a single observation by station and date.
        
        Args:
            station_id: NOAA station identifier
            observation_date: Date of observation
            
        Returns:
            WeatherObservation: The matching observation, or None if not found
        """
        return self.repository.get_observation(station_id, observation_date)

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        """Ingest or update yearly statistics for a station.
        
        Args:
            stat: WeatherYearlyStatCreate schema with aggregated statistics
            
        Returns:
            WeatherYearlyStat: The inserted or updated ORM model instance
        """
        return self.repository.upsert_yearly_stat(stat)

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        """List all yearly statistics for a station.
        
        Args:
            station_id: NOAA station identifier
            
        Returns:
            Sequence[WeatherYearlyStat]: All yearly statistics for the station,
                or empty sequence if none found
        """
        return self.repository.list_yearly_stats(station_id)
