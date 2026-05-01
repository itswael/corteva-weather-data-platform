"""SQLAlchemy implementation of the weather repository.

This module provides a concrete implementation of the WeatherRepository
protocol using SQLAlchemy ORM for PostgreSQL/SQLite persistence.
"""
from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class SQLAlchemyWeatherRepository(WeatherRepository):
    """SQLAlchemy-based implementation of WeatherRepository.
    
    Uses PostgreSQL's ON CONFLICT DO UPDATE/DO NOTHING for idempotent
    upserts. Automatically handles duplicate key violations safely.
    
    Attributes:
        session: SQLAlchemy Session for database operations
    """
    def __init__(self, session: Session) -> None:
        """Initialize repository with a database session.
        
        Args:
            session: SQLAlchemy Session instance for database operations
        """
        self.session = session

    def upsert_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        """Insert or update a weather observation (upsert).
        
        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE to upsert on the
        (station_id, observation_date) unique constraint. If a record with
        the same station/date exists, it updates the measurements and source_file.
        
        Args:
            observation: WeatherObservationCreate schema with observation data
            
        Returns:
            WeatherObservation: The inserted or updated observation ORM model
        """
        statement = (
            insert(WeatherObservation)
            .values(**observation.model_dump())
            .on_conflict_do_update(
        """Insert observation only if not already present (idempotent insert).
        
        Uses PostgreSQL INSERT ... ON CONFLICT DO NOTHING to silently ignore
        duplicate key violations. Enables safe re-runs and batch ingestion.
        
        Args:
            observation: WeatherObservationCreate schema with observation data
            
        Returns:
            bool: True if new record was inserted, False if skipped as duplicate
        """
                index_elements=[WeatherObservation.station_id, WeatherObservation.observation_date],
                set_={
                    "max_temp_c": observation.max_temp_c,
                    "min_temp_c": observation.min_temp_c,
                    "precipitation_cm": observation.precipitation_cm,
                    "source_file": observation.source_file,
                },
            )
        )
        self.session.execute(statement)
        self.session.commit()
        return self.get_observation(
            observation.station_id,
            observation.observation_date,
        )  # type: ignore[return-value]

    def insert_observation_if_missing(self, observation: WeatherObservationCreate) -> bool:
        statement = (
        """Retrieve a single observation by station and date.
        
        Args:
            station_id: NOAA station identifier
            observation_date: Date of observation
            
        Returns:
            WeatherObservation: The matching observation, or None if not found
        """
            insert(WeatherObservation)
            .values(**observation.model_dump())
            .on_conflict_do_nothing(
                index_elements=[WeatherObservation.station_id, WeatherObservation.observation_date]
            )
        )
        result = self.session.execute(statement)
        self.session.commit()
        return result.rowcount == 1
"""Insert or update yearly statistics for a station.
        
        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE to upsert on the
        (station_id, year) unique constraint.
        
        Args:
            stat: WeatherYearlyStatCreate schema with aggregated statistics
            
        Returns:
            WeatherYearlyStat: The inserted or updated yearly stat ORM model
        """
        
    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        statement = select(WeatherObservation).where(
            WeatherObservation.station_id == station_id,
            WeatherObservation.observation_date == observation_date,
        )
        return self.session.scalars(statement).one_or_none()

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        statement = (
            insert(WeatherYearlyStat)
            .values(**stat.model_dump())
        """Retrieve all yearly statistics for a station.
        
        Args:
            station_id: NOAA station identifier
            
        Returns:
            Sequence[WeatherYearlyStat]: All yearly statistics for the station,
                or empty sequence if none found
        """
            .on_conflict_do_update(
                index_elements=[WeatherYearlyStat.station_id, WeatherYearlyStat.year],
                set_={
                    "avg_max_temp_c": stat.avg_max_temp_c,
                    "avg_min_temp_c": stat.avg_min_temp_c,
                    "total_precipitation_cm": stat.total_precipitation_cm,
                    "observation_count": stat.observation_count,
                },
            )
        )
        self.session.execute(statement)
        self.session.commit()
        return self.session.scalars(
            select(WeatherYearlyStat).where(
                WeatherYearlyStat.station_id == stat.station_id,
                WeatherYearlyStat.year == stat.year,
            )
        ).one()

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        statement = (
            select(WeatherYearlyStat)
            .where(WeatherYearlyStat.station_id == station_id)
            .order_by(WeatherYearlyStat.year.asc())
        )
        return self.session.scalars(statement).all()
