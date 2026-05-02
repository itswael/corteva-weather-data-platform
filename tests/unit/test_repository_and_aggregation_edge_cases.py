from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from sqlalchemy.orm import Session

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import YearlyAggregateData
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.schemas.weather import WeatherYearlyStatCreate
from weather_platform.services.aggregation import WeatherAggregationService


def _add_observation(
    session: Session,
    *,
    station_id: str,
    observation_date,
    max_temp_c,
    min_temp_c,
    precipitation_cm,
) -> WeatherObservation:
    record_id = session.query(WeatherObservation).count() + 1
    observation = WeatherObservation(
        id=record_id,
        station_id=station_id,
        observation_date=observation_date,
        max_temp_c=max_temp_c,
        min_temp_c=min_temp_c,
        precipitation_cm=precipitation_cm,
        source_file=f"{station_id}.txt",
    )
    session.add(observation)
    session.commit()
    return observation


def _add_yearly_stat(
    session: Session,
    *,
    station_id: str,
    year: int,
    avg_max_temp_c: Decimal | None,
    avg_min_temp_c: Decimal | None,
    total_precipitation_cm: Decimal | None,
    observation_count: int,
) -> WeatherYearlyStat:
    record_id = session.query(WeatherYearlyStat).count() + 1
    yearly_stat = WeatherYearlyStat(
        id=record_id,
        station_id=station_id,
        year=year,
        avg_max_temp_c=avg_max_temp_c,
        avg_min_temp_c=avg_min_temp_c,
        total_precipitation_cm=total_precipitation_cm,
        observation_count=observation_count,
    )
    session.add(yearly_stat)
    session.commit()
    return yearly_stat


class TestRepositoryAggregationEdgeCases:
    """Repository tests focused on missing values and pagination edge cases."""

    def test_aggregate_yearly_observations_ignores_missing_measurements(
        self, db_session: Session
    ) -> None:
        """Aggregate queries should ignore NULL values but still count rows."""
        _add_observation(
            db_session,
            station_id="USC00110072",
            observation_date=datetime(2024, 1, 1).date(),
            max_temp_c=Decimal("20.00"),
            min_temp_c=Decimal("10.00"),
            precipitation_cm=Decimal("1.00"),
        )
        _add_observation(
            db_session,
            station_id="USC00110072",
            observation_date=datetime(2024, 1, 2).date(),
            max_temp_c=None,
            min_temp_c=Decimal("12.00"),
            precipitation_cm=None,
        )
        _add_observation(
            db_session,
            station_id="USC00110072",
            observation_date=datetime(2024, 1, 3).date(),
            max_temp_c=Decimal("22.00"),
            min_temp_c=None,
            precipitation_cm=Decimal("0.50"),
        )

        repository = SQLAlchemyWeatherRepository(db_session)
        aggregate = repository.aggregate_yearly_observations("USC00110072", 2024)

        assert aggregate.avg_max_temp_c == Decimal("21.00")
        assert aggregate.avg_min_temp_c == Decimal("11.00")
        assert aggregate.total_precipitation_cm == Decimal("1.50")
        assert aggregate.observation_count == 3

    def test_aggregate_yearly_observations_returns_none_when_all_measurements_missing(
        self, db_session: Session
    ) -> None:
        """Aggregate queries should preserve None when all measurements are missing."""
        _add_observation(
            db_session,
            station_id="USC00110072",
            observation_date=datetime(2024, 2, 1).date(),
            max_temp_c=None,
            min_temp_c=None,
            precipitation_cm=None,
        )
        _add_observation(
            db_session,
            station_id="USC00110072",
            observation_date=datetime(2024, 2, 2).date(),
            max_temp_c=None,
            min_temp_c=None,
            precipitation_cm=None,
        )

        repository = SQLAlchemyWeatherRepository(db_session)
        aggregate = repository.aggregate_yearly_observations("USC00110072", 2024)

        assert aggregate.avg_max_temp_c is None
        assert aggregate.avg_min_temp_c is None
        assert aggregate.total_precipitation_cm is None
        assert aggregate.observation_count == 2

    def test_query_yearly_stats_paginates_and_orders_descending(
        self, db_session: Session
    ) -> None:
        """Yearly stats queries should respect filters, pagination, and ordering."""
        _add_yearly_stat(
            db_session,
            station_id="USC00110072",
            year=2021,
            avg_max_temp_c=Decimal("23.00"),
            avg_min_temp_c=Decimal("11.00"),
            total_precipitation_cm=Decimal("100.00"),
            observation_count=10,
        )
        _add_yearly_stat(
            db_session,
            station_id="USC00110072",
            year=2022,
            avg_max_temp_c=Decimal("24.00"),
            avg_min_temp_c=Decimal("12.00"),
            total_precipitation_cm=Decimal("110.00"),
            observation_count=11,
        )
        _add_yearly_stat(
            db_session,
            station_id="USC00110072",
            year=2023,
            avg_max_temp_c=Decimal("25.00"),
            avg_min_temp_c=Decimal("13.00"),
            total_precipitation_cm=Decimal("120.00"),
            observation_count=12,
        )
        _add_yearly_stat(
            db_session,
            station_id="USC00250070",
            year=2023,
            avg_max_temp_c=Decimal("19.00"),
            avg_min_temp_c=Decimal("9.00"),
            total_precipitation_cm=Decimal("90.00"),
            observation_count=12,
        )

        repository = SQLAlchemyWeatherRepository(db_session)
        page, total = repository.query_yearly_stats(
            skip=1,
            limit=1,
            station_id="USC00110072",
            start_year=2021,
            end_year=2023,
        )

        assert total == 3
        assert len(page) == 1
        assert page[0].year == 2022
        assert page[0].station_id == "USC00110072"

    def test_query_yearly_stats_returns_empty_for_missing_station(
        self, db_session: Session
    ) -> None:
        """Yearly stats queries should return empty results when no rows match."""
        repository = SQLAlchemyWeatherRepository(db_session)

        page, total = repository.query_yearly_stats(station_id="DOES_NOT_EXIST")

        assert page == []
        assert total == 0


class TestAggregationServiceEdgeCases:
    """Aggregation service tests using dependency-injected repository mocks."""

    def test_aggregate_year_preserves_missing_measurements(self) -> None:
        """Service should pass through missing aggregates without inventing values."""
        repository = Mock()
        repository.aggregate_yearly_observations.return_value = YearlyAggregateData(
            avg_max_temp_c=None,
            avg_min_temp_c=Decimal("8.75"),
            total_precipitation_cm=None,
            observation_count=4,
        )
        repository.upsert_yearly_stat.return_value = WeatherYearlyStat(
            id=99,
            station_id="USC00110072",
            year=2024,
            avg_max_temp_c=None,
            avg_min_temp_c=Decimal("8.75"),
            total_precipitation_cm=None,
            observation_count=4,
            created_at=datetime.now(),
        )

        service = WeatherAggregationService(repository)
        stat, summary = service.aggregate_year("USC00110072", 2024)

        called_stat = repository.upsert_yearly_stat.call_args.args[0]
        assert called_stat.avg_max_temp_c is None
        assert called_stat.avg_min_temp_c == Decimal("8.75")
        assert called_stat.total_precipitation_cm is None
        assert called_stat.observation_count == 4
        assert stat.id == 99
        assert summary.observations_processed == 4
        assert summary.measurements_available == {
            "max_temp": False,
            "min_temp": True,
            "precipitation": False,
        }

    def test_aggregate_year_range_returns_empty_for_inverted_range(self) -> None:
        """Service should return no summaries when the year range is empty."""
        repository = Mock()
        service = WeatherAggregationService(repository)

        summaries = service.aggregate_year_range("USC00110072", 2024, 2023)

        assert summaries == []
        repository.aggregate_yearly_observations.assert_not_called()
        repository.upsert_yearly_stat.assert_not_called()
