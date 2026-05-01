"""Tests for yearly weather aggregation service."""
import pytest
from datetime import date
from decimal import Decimal

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.services.aggregation import WeatherAggregationService
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate
from sqlalchemy.orm import Session


def test_aggregate_year_with_mixed_null_values(db_session: Session) -> None:
    """Test aggregation handles NULL values correctly, ignoring them in calculations.
    
    Creates observations with various NULL patterns and verifies:
    - NULL values are excluded from averages
    - NULL values are excluded from sums
    - Observation count reflects total records (including those with some NULLs)
    """
    from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
    
    repo = SQLAlchemyWeatherRepository(db_session)
    service = WeatherAggregationService(repo)
    station_id = "TEST_STATION"
    year = 2023
    
    # Add observations with various NULL patterns
    observations = [
        # Day 1: All values
        WeatherObservationCreate(
            station_id=station_id,
            observation_date=date(2023, 1, 1),
            max_temp_c=Decimal("20.0"),
            min_temp_c=Decimal("10.0"),
            precipitation_cm=Decimal("5.0"),
        ),
        # Day 2: No precipitation
        WeatherObservationCreate(
            station_id=station_id,
            observation_date=date(2023, 1, 2),
            max_temp_c=Decimal("22.0"),
            min_temp_c=Decimal("12.0"),
            precipitation_cm=None,
        ),
        # Day 3: No temperatures
        WeatherObservationCreate(
            station_id=station_id,
            observation_date=date(2023, 1, 3),
            max_temp_c=None,
            min_temp_c=None,
            precipitation_cm=Decimal("2.0"),
        ),
        # Day 4: Only max temp
        WeatherObservationCreate(
            station_id=station_id,
            observation_date=date(2023, 1, 4),
            max_temp_c=Decimal("18.0"),
            min_temp_c=None,
            precipitation_cm=None,
        ),
    ]
    
    for obs in observations:
        repo.upsert_observation(obs)
    
    # Aggregate for 2023
    yearly_stat, summary = service.aggregate_year(station_id, year)
    
    # Verify aggregation ignores NULLs
    # Max temps: 20, 22, 18 (exclude day 3) = avg 20.0
    assert yearly_stat.avg_max_temp_c == Decimal("20.00")
    
    # Min temps: 10, 12 (exclude day 3 and 4) = avg 11.0
    assert yearly_stat.avg_min_temp_c == Decimal("11.00")
    
    # Precipitation: 5, 2 (exclude day 1 no precip... wait let me recalc)
    # Actually day 1 has 5, day 2 has None, day 3 has 2, day 4 has None = 5 + 2 = 7
    assert yearly_stat.total_precipitation_cm == Decimal("7.00")
    
    # Observation count = 4 (all days counted)
    assert yearly_stat.observation_count == 4
    
    # Verify summary
    assert summary.station_id == station_id
    assert summary.year == year
    assert summary.observations_processed == 4
    assert summary.measurements_available["max_temp"] is True
    assert summary.measurements_available["min_temp"] is True
    assert summary.measurements_available["precipitation"] is True


def test_aggregate_year_range(db_session: Session) -> None:
    """Test aggregation of multiple years in sequence."""
    from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
    
    repo = SQLAlchemyWeatherRepository(db_session)
    service = WeatherAggregationService(repo)
    station_id = "TEST_MULTI_YEAR"
    
    # Add observations for 3 different years
    for year in [2021, 2022, 2023]:
        obs = WeatherObservationCreate(
            station_id=station_id,
            observation_date=date(year, 6, 15),
            max_temp_c=Decimal(str(15 + year - 2021)),
            min_temp_c=Decimal(str(5 + year - 2021)),
            precipitation_cm=Decimal(str(10 + year - 2021)),
        )
        repo.upsert_observation(obs)
    
    # Aggregate all years
    summaries = service.aggregate_year_range(station_id, 2021, 2023)
    
    assert len(summaries) == 3
    assert summaries[0].year == 2021
    assert summaries[1].year == 2022
    assert summaries[2].year == 2023
    
    # Verify each year has 1 observation
    for summary in summaries:
        assert summary.observations_processed == 1


def test_aggregate_year_with_all_nulls(db_session: Session) -> None:
    """Test aggregation when all measurement values are NULL."""
    from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
    
    repo = SQLAlchemyWeatherRepository(db_session)
    service = WeatherAggregationService(repo)
    station_id = "TEST_ALL_NULL"
    year = 2023
    
    # Add observations with all NULL measurements
    obs = WeatherObservationCreate(
        station_id=station_id,
        observation_date=date(2023, 1, 1),
        max_temp_c=None,
        min_temp_c=None,
        precipitation_cm=None,
    )
    repo.upsert_observation(obs)
    
    yearly_stat, summary = service.aggregate_year(station_id, year)
    
    # All measurement aggregates should be None
    assert yearly_stat.avg_max_temp_c is None
    assert yearly_stat.avg_min_temp_c is None
    assert yearly_stat.total_precipitation_cm is None
    assert yearly_stat.observation_count == 1
    
    # No measurements available
    assert summary.measurements_available == {
        "max_temp": False,
        "min_temp": False,
        "precipitation": False,
    }


def test_get_yearly_stats_ordered(db_session: Session) -> None:
    """Test retrieval of yearly statistics returns results ordered by year."""
    from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
    
    repo = SQLAlchemyWeatherRepository(db_session)
    service = WeatherAggregationService(repo)
    station_id = "TEST_ORDERED"
    
    # Insert stats in random order
    for year in [2023, 2021, 2022]:
        stat = WeatherYearlyStatCreate(
            station_id=station_id,
            year=year,
            avg_max_temp_c=Decimal("20.00"),
            avg_min_temp_c=Decimal("10.00"),
            total_precipitation_cm=Decimal("100.00"),
            observation_count=365,
        )
        repo.upsert_yearly_stat(stat)
    
    stats = service.get_yearly_stats(station_id)
    
    # Verify ordered by year ascending
    assert len(stats) == 3
    assert stats[0].year == 2021
    assert stats[1].year == 2022
    assert stats[2].year == 2023
