from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import func, and_, extract, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository, YearlyAggregateData
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class SQLAlchemyWeatherRepository(WeatherRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        statement = (
            insert(WeatherObservation)
            .values(**observation.model_dump())
            .on_conflict_do_update(
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

    def aggregate_yearly_observations(
        self, station_id: str, year: int
    ) -> YearlyAggregateData:
        """Calculate yearly aggregates from observations, ignoring NULL values.
        
        Uses SQL aggregate functions to calculate:
        - avg(max_temp_c) for non-NULL records
        - avg(min_temp_c) for non-NULL records
        - sum(precipitation_cm) for non-NULL records
        - count(*) of observations in the year
        
        Args:
            station_id: NOAA station identifier
            year: Calendar year for aggregation
            
        Returns:
            YearlyAggregateData: Aggregated measurements
        """
        # Build query to aggregate observations by station/year
        # extract(year, date) requires the observation_date column
        statement = select(
            func.avg(WeatherObservation.max_temp_c).label("avg_max_temp_c"),
            func.avg(WeatherObservation.min_temp_c).label("avg_min_temp_c"),
            func.sum(WeatherObservation.precipitation_cm).label("total_precipitation_cm"),
            func.count(WeatherObservation.id).label("observation_count"),
        ).where(
            and_(
                WeatherObservation.station_id == station_id,
                extract("year", WeatherObservation.observation_date) == year,
            )
        )

        # Execute and extract results
        result = self.session.execute(statement).one()
        
        # Build result object with Decimal conversion for consistency
        return YearlyAggregateData(
            avg_max_temp_c=Decimal(str(result.avg_max_temp_c)) if result.avg_max_temp_c is not None else None,
            avg_min_temp_c=Decimal(str(result.avg_min_temp_c)) if result.avg_min_temp_c is not None else None,
            total_precipitation_cm=Decimal(str(result.total_precipitation_cm)) if result.total_precipitation_cm is not None else None,
            observation_count=result.observation_count or 0,
        )
