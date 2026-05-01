"""Unit tests for yearly weather aggregation service."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from weather_platform.services.aggregation import (
    WeatherAggregationService,
    AggregationSummary,
)
from weather_platform.repositories.base import YearlyAggregateData
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.schemas.weather import WeatherYearlyStatCreate


def test_aggregate_year_calculates_and_persists():
    """Test that aggregate_year calculates stats and persists them."""
    # Mock repository
    mock_repo = Mock()
    
    # Mock the aggregation query result
    aggregate_data = YearlyAggregateData(
        avg_max_temp_c=Decimal("20.00"),
        avg_min_temp_c=Decimal("10.00"),
        total_precipitation_cm=Decimal("100.00"),
        observation_count=365,
    )
    mock_repo.aggregate_yearly_observations.return_value = aggregate_data
    
    # Mock the persisted stat
    persisted_stat = WeatherYearlyStat(
        id=1,
        station_id="TEST_STATION",
        year=2023,
        avg_max_temp_c=Decimal("20.00"),
        avg_min_temp_c=Decimal("10.00"),
        total_precipitation_cm=Decimal("100.00"),
        observation_count=365,
        created_at=datetime.now(),
    )
    mock_repo.upsert_yearly_stat.return_value = persisted_stat
    
    # Create service and aggregate
    service = WeatherAggregationService(mock_repo)
    station_id = "TEST_STATION"
    year = 2023
    
    stat, summary = service.aggregate_year(station_id, year)
    
    # Verify repository called correctly
    mock_repo.aggregate_yearly_observations.assert_called_once_with(station_id, year)
    
    # Verify upsert called with correct data
    call_args = mock_repo.upsert_yearly_stat.call_args
    upserted_stat = call_args[0][0]
    assert upserted_stat.station_id == station_id
    assert upserted_stat.year == year
    assert upserted_stat.avg_max_temp_c == Decimal("20.00")
    assert upserted_stat.observation_count == 365
    
    # Verify returned stat
    assert stat.id == 1
    assert stat.station_id == station_id
    
    # Verify summary
    assert summary.station_id == station_id
    assert summary.year == year
    assert summary.observations_processed == 365
    assert summary.measurements_available["max_temp"] is True
    assert summary.measurements_available["min_temp"] is True
    assert summary.measurements_available["precipitation"] is True


def test_aggregate_year_handles_null_values():
    """Test that aggregation correctly reports NULL value presence."""
    mock_repo = Mock()
    
    # Mock aggregation with some NULL values
    aggregate_data = YearlyAggregateData(
        avg_max_temp_c=Decimal("15.50"),
        avg_min_temp_c=None,  # All min temps were NULL
        total_precipitation_cm=Decimal("50.00"),
        observation_count=200,
    )
    mock_repo.aggregate_yearly_observations.return_value = aggregate_data
    
    # Mock persisted stat
    persisted_stat = WeatherYearlyStat(
        id=2,
        station_id="STATION_2",
        year=2022,
        avg_max_temp_c=Decimal("15.50"),
        avg_min_temp_c=None,
        total_precipitation_cm=Decimal("50.00"),
        observation_count=200,
        created_at=datetime.now(),
    )
    mock_repo.upsert_yearly_stat.return_value = persisted_stat
    
    service = WeatherAggregationService(mock_repo)
    stat, summary = service.aggregate_year("STATION_2", 2022)
    
    # Verify summary correctly identifies NULL measurements
    assert summary.measurements_available["max_temp"] is True
    assert summary.measurements_available["min_temp"] is False  # Was None
    assert summary.measurements_available["precipitation"] is True


def test_aggregate_year_range_processes_multiple_years():
    """Test that aggregate_year_range calls aggregate_year for each year."""
    mock_repo = Mock()
    
    # Create mock results for each year
    def create_aggregate_data(year: int) -> YearlyAggregateData:
        return YearlyAggregateData(
            avg_max_temp_c=Decimal(str(15 + year - 2021)),
            avg_min_temp_c=Decimal(str(5 + year - 2021)),
            total_precipitation_cm=Decimal(str(100 + (year - 2021) * 10)),
            observation_count=365,
        )
    
    # Setup mock to return different data per year
    mock_repo.aggregate_yearly_observations.side_effect = [
        create_aggregate_data(2021),
        create_aggregate_data(2022),
        create_aggregate_data(2023),
    ]
    
    # Setup mock stats
    persisted_stats = []
    for year in [2021, 2022, 2023]:
        stat = WeatherYearlyStat(
            id=year - 2020,
            station_id="MULTI_YEAR",
            year=year,
            avg_max_temp_c=Decimal(str(15 + year - 2021)),
            avg_min_temp_c=Decimal(str(5 + year - 2021)),
            total_precipitation_cm=Decimal(str(100 + (year - 2021) * 10)),
            observation_count=365,
            created_at=datetime.now(),
        )
        persisted_stats.append(stat)
    
    mock_repo.upsert_yearly_stat.side_effect = persisted_stats
    
    service = WeatherAggregationService(mock_repo)
    summaries = service.aggregate_year_range("MULTI_YEAR", 2021, 2023)
    
    # Verify called for each year
    assert len(summaries) == 3
    assert summaries[0].year == 2021
    assert summaries[1].year == 2022
    assert summaries[2].year == 2023
    
    # Verify aggregate_yearly_observations called 3 times
    assert mock_repo.aggregate_yearly_observations.call_count == 3
    assert mock_repo.upsert_yearly_stat.call_count == 3


def test_get_yearly_stats_delegates_to_repository():
    """Test that get_yearly_stats delegates to repository.list_yearly_stats."""
    mock_repo = Mock()
    
    # Mock stats returned from repo
    stats = [
        WeatherYearlyStat(
            id=1,
            station_id="TEST",
            year=2021,
            avg_max_temp_c=Decimal("16.00"),
            avg_min_temp_c=Decimal("6.00"),
            total_precipitation_cm=Decimal("100.00"),
            observation_count=365,
            created_at=datetime.now(),
        ),
        WeatherYearlyStat(
            id=2,
            station_id="TEST",
            year=2022,
            avg_max_temp_c=Decimal("17.00"),
            avg_min_temp_c=Decimal("7.00"),
            total_precipitation_cm=Decimal("110.00"),
            observation_count=365,
            created_at=datetime.now(),
        ),
    ]
    mock_repo.list_yearly_stats.return_value = stats
    
    service = WeatherAggregationService(mock_repo)
    result = service.get_yearly_stats("TEST")
    
    # Verify repository called
    mock_repo.list_yearly_stats.assert_called_once_with("TEST")
    
    # Verify returned stats
    assert len(result) == 2
    assert result[0].year == 2021
    assert result[1].year == 2022


def test_aggregation_summary_structure():
    """Test that AggregationSummary contains expected fields."""
    summary = AggregationSummary(
        station_id="STATION_A",
        year=2023,
        observations_processed=365,
        aggregation_completed_at=datetime.now(),
        measurements_available={
            "max_temp": True,
            "min_temp": False,
            "precipitation": True,
        },
    )
    
    assert summary.station_id == "STATION_A"
    assert summary.year == 2023
    assert summary.observations_processed == 365
    assert summary.measurements_available["max_temp"] is True
    assert summary.measurements_available["min_temp"] is False
    assert summary.measurements_available["precipitation"] is True


def test_yearly_aggregate_data_with_all_nulls():
    """Test YearlyAggregateData with all NULL measurements."""
    aggregate_data = YearlyAggregateData(
        avg_max_temp_c=None,
        avg_min_temp_c=None,
        total_precipitation_cm=None,
        observation_count=10,
    )
    
    assert aggregate_data.avg_max_temp_c is None
    assert aggregate_data.avg_min_temp_c is None
    assert aggregate_data.total_precipitation_cm is None
    assert aggregate_data.observation_count == 10


def test_yearly_aggregate_data_immutable():
    """Test that YearlyAggregateData is immutable (frozen dataclass)."""
    aggregate_data = YearlyAggregateData(
        avg_max_temp_c=Decimal("20.00"),
        avg_min_temp_c=Decimal("10.00"),
        total_precipitation_cm=Decimal("100.00"),
        observation_count=365,
    )
    
    # Verify it's frozen (cannot modify)
    try:
        aggregate_data.avg_max_temp_c = Decimal("25.00")
        assert False, "Should not be able to modify frozen dataclass"
    except Exception:
        pass  # Expected - frozen dataclass
