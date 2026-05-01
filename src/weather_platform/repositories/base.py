"""Repository interface (protocol) for weather data persistence.

This module defines the WeatherRepository protocol, which establishes the
contract that all repository implementations must satisfy. This enables
loose coupling between service and data access layers.
"""
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class WeatherRepository(Protocol):
    """Protocol defining the contract for weather data repositories.
    
    Any class implementing this protocol can be used as a repository,
    enabling polymorphism and testability (e.g., fake repositories for tests).
    
    Methods:
        upsert_observation: Insert or update a single observation
        insert_observation_if_missing: Insert only if not already present
        get_observation: Retrieve a single observation by station and date
        upsert_yearly_stat: Insert or update yearly statistics
        list_yearly_stats: Retrieve all yearly stats for a station
    """

    def upsert_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        """Insert or update a weather observation.
        
        Uses ON CONFLICT DO UPDATE to upsert on (station_id, observation_date).
        Overwrites existing measurements for the same station/date.
        
        Args:
            observation: WeatherObservationCreate schema with observation data
            
        Returns:
            WeatherObservation: The inserted or updated observation
        """
        ...

    def insert_observation_if_missing(self, observation: WeatherObservationCreate) -> bool:
        """Insert observation only if not already present (idempotent).
        
        Uses ON CONFLICT DO NOTHING to skip duplicates. Enables safe re-runs
        of ingestion without worrying about duplicate errors.
        
        Args:
            observation: WeatherObservationCreate schema with observation data
            
        Returns:
            bool: True if new record was inserted, False if skipped as duplicate
        """
        ...

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        """Retrieve a single observation by station and date.
        
        Args:
            station_id: NOAA station identifier
            observation_date: Date of observation
            
        Returns:
            WeatherObservation: The matching observation, or None if not found
        """
        ...

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        """Insert or update yearly statistics for a station.
        
        Uses ON CONFLICT DO UPDATE to upsert on (station_id, year).
        
        Args:
            stat: WeatherYearlyStatCreate schema with aggregated statistics
            
        Returns:
            WeatherYearlyStat: The inserted or updated yearly stat
        """
        ...

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        """Retrieve all yearly statistics for a station.
        
        Args:
            station_id: NOAA station identifier
            
        Returns:
            Sequence[WeatherYearlyStat]: All yearly statistics for the station,
                or empty sequence if none found
        """
        ...
