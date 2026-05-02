"""Unit tests for weather observation query functionality with pagination and filtering."""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService
from weather_platform.schemas.weather import PaginatedWeatherObservationRead


def test_query_observations_with_pagination():
    """Test that query_observations returns paginated results with total count."""
    # Create mock observations
    obs1 = WeatherObservation(
        id=1,
        station_id="USC00110072",
        observation_date=date(2023, 1, 1),
        max_temp_c=Decimal("15.00"),
        min_temp_c=Decimal("5.00"),
        precipitation_cm=Decimal("0.00"),
        source_file="test.txt",
        created_at=datetime.now(),
    )
    obs2 = WeatherObservation(
        id=2,
        station_id="USC00110072",
        observation_date=date(2023, 1, 2),
        max_temp_c=Decimal("16.00"),
        min_temp_c=Decimal("6.00"),
        precipitation_cm=Decimal("1.00"),
        source_file="test.txt",
        created_at=datetime.now(),
    )

    # Mock repository
    mock_repo = Mock()
    mock_repo.query_observations.return_value = ([obs1, obs2], 100)

    # Create service
    service = WeatherService(mock_repo)

    # Query with pagination
    result = service.query_observations(skip=0, limit=2)

    # Verify pagination metadata
    assert isinstance(result, PaginatedWeatherObservationRead)
    assert result.skip == 0
    assert result.limit == 2
    assert result.total == 100
    assert len(result.items) == 2
    assert result.items[0].id == 1
    assert result.items[1].id == 2


def test_query_observations_with_station_filter():
    """Test that query_observations passes station_id filter to repository."""
    mock_repo = Mock()
    mock_repo.query_observations.return_value = ([], 0)

    service = WeatherService(mock_repo)

    # Query with station_id filter
    service.query_observations(
        skip=0,
        limit=50,
        station_id="USC00110072",
    )

    # Verify repository called with correct filter
    mock_repo.query_observations.assert_called_once()
    call_kwargs = mock_repo.query_observations.call_args.kwargs
    assert call_kwargs["station_id"] == "USC00110072"
    assert call_kwargs["skip"] == 0
    assert call_kwargs["limit"] == 50


def test_query_observations_with_date_range_filter():
    """Test that query_observations passes date range filters to repository."""
    mock_repo = Mock()
    mock_repo.query_observations.return_value = ([], 0)

    service = WeatherService(mock_repo)

    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    # Query with date range filter
    service.query_observations(
        skip=0,
        limit=50,
        start_date=start,
        end_date=end,
    )

    # Verify repository called with correct filters
    mock_repo.query_observations.assert_called_once()
    call_kwargs = mock_repo.query_observations.call_args.kwargs
    assert call_kwargs["start_date"] == start
    assert call_kwargs["end_date"] == end


def test_query_observations_caps_limit():
    """Test that query_observations enforces maximum limit of 1000."""
    mock_repo = Mock()
    mock_repo.query_observations.return_value = ([], 0)

    service = WeatherService(mock_repo)

    # Request with limit > 1000
    service.query_observations(skip=0, limit=5000)

    # Verify limit was capped to 1000
    call_kwargs = mock_repo.query_observations.call_args.kwargs
    assert call_kwargs["limit"] == 1000


def test_query_observations_returns_paginated_response():
    """Test that query_observations returns proper pagination metadata."""
    obs = WeatherObservation(
        id=1,
        station_id="USC00110072",
        observation_date=date(2023, 1, 1),
        max_temp_c=Decimal("15.00"),
        min_temp_c=Decimal("5.00"),
        precipitation_cm=Decimal("0.00"),
        source_file="test.txt",
        created_at=datetime.now(),
    )

    mock_repo = Mock()
    mock_repo.query_observations.return_value = ([obs], 250)

    service = WeatherService(mock_repo)

    result = service.query_observations(skip=10, limit=25)

    # Verify response structure
    assert result.skip == 10
    assert result.limit == 25
    assert result.total == 250
    assert len(result.items) == 1
    assert result.items[0].station_id == "USC00110072"
    assert result.items[0].observation_date == date(2023, 1, 1)
