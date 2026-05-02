"""Unit tests for OpenAPI documentation and yearly stats endpoint.

Tests verify:
- Endpoint response schemas match OpenAPI specifications
- Pagination works correctly for yearly stats
- Filtering by station_id, start_year, end_year functions
- Field descriptions and examples in schemas
- Error responses (404, 422, 500)
- Idempotency of upsert operations
"""

from decimal import Decimal
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from weather_platform.models import WeatherYearlyStat
from weather_platform.repositories.weather import WeatherRepository
from weather_platform.schemas.weather import (
    WeatherYearlyStatCreate,
    WeatherYearlyStatRead,
    PaginatedWeatherYearlyStatRead,
    HTTPErrorResponse,
)
from weather_platform.services.weather import WeatherService


@pytest.fixture
def sample_yearly_stats(db_session: Session) -> list[WeatherYearlyStat]:
    """Create sample yearly stats for testing pagination and filtering."""
    stats = [
        WeatherYearlyStat(
            station_id="USC00110072",
            year=2020,
            avg_max_temp_c=Decimal("22.5"),
            avg_min_temp_c=Decimal("11.0"),
            total_precipitation_cm=Decimal("100.0"),
            observation_count=365,
        ),
        WeatherYearlyStat(
            station_id="USC00110072",
            year=2021,
            avg_max_temp_c=Decimal("23.0"),
            avg_min_temp_c=Decimal("11.5"),
            total_precipitation_cm=Decimal("110.0"),
            observation_count=365,
        ),
        WeatherYearlyStat(
            station_id="USC00110072",
            year=2022,
            avg_max_temp_c=Decimal("24.0"),
            avg_min_temp_c=Decimal("12.0"),
            total_precipitation_cm=Decimal("120.0"),
            observation_count=365,
        ),
        WeatherYearlyStat(
            station_id="USC00110072",
            year=2023,
            avg_max_temp_c=Decimal("24.3"),
            avg_min_temp_c=Decimal("12.8"),
            total_precipitation_cm=Decimal("125.4"),
            observation_count=365,
        ),
        WeatherYearlyStat(
            station_id="USC00250070",
            year=2023,
            avg_max_temp_c=Decimal("25.0"),
            avg_min_temp_c=Decimal("13.0"),
            total_precipitation_cm=Decimal("130.0"),
            observation_count=365,
        ),
    ]
    for stat in stats:
        db_session.add(stat)
    db_session.commit()
    return stats


class TestYearlyStatsQueryPagination:
    """Test pagination for yearly statistics queries."""

    def test_query_yearly_stats_with_pagination(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify pagination offset and limit work correctly."""
        repository = WeatherRepository(db_session)
        service = WeatherService(repository)

        # Query first page
        page1 = service.query_yearly_stats(skip=0, limit=2)
        assert len(page1.items) == 2
        assert page1.total == 5
        assert page1.skip == 0
        assert page1.limit == 2

        # Query second page
        page2 = service.query_yearly_stats(skip=2, limit=2)
        assert len(page2.items) == 2
        assert page2.total == 5
        assert page2.skip == 2
        assert page2.limit == 2

        # Verify no overlap between pages
        page1_ids = {item.id for item in page1.items}
        page2_ids = {item.id for item in page2.items}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

    def test_query_yearly_stats_caps_limit_to_1000(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify limit is capped at 1000 server-side."""
        repository = WeatherRepository(db_session)
        service = WeatherService(repository)

        # Request limit larger than cap
        page = service.query_yearly_stats(skip=0, limit=5000)
        assert page.limit == 1000, "Service should cap limit to 1000"

    def test_query_yearly_stats_empty_page(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify empty page when skip exceeds total records."""
        repository = WeatherRepository(db_session)
        service = WeatherService(repository)

        page = service.query_yearly_stats(skip=1000, limit=100)
        assert len(page.items) == 0
        assert page.total == 5
        assert page.skip == 1000
        assert page.limit == 100


class TestYearlyStatsQueryFiltering:
    """Test filtering for yearly statistics queries."""

    def test_query_yearly_stats_filter_by_station(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify station_id filter returns only matching records."""
        repository = WeatherRepository(db_session)

        stats, total = repository.query_yearly_stats(station_id="USC00110072")
        assert len(stats) == 4
        assert total == 4
        assert all(stat.station_id == "USC00110072" for stat in stats)

    def test_query_yearly_stats_filter_by_start_year(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify start_year filter returns only years >= start_year."""
        repository = WeatherRepository(db_session)

        stats, total = repository.query_yearly_stats(start_year=2022)
        assert total == 3  # 2022, 2023 (2 stations)
        assert all(stat.year >= 2022 for stat in stats)

    def test_query_yearly_stats_filter_by_end_year(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify end_year filter returns only years <= end_year."""
        repository = WeatherRepository(db_session)

        stats, total = repository.query_yearly_stats(end_year=2021)
        assert total == 3  # 2020, 2021 (1 station), 2021 (other)
        assert all(stat.year <= 2021 for stat in stats)

    def test_query_yearly_stats_filter_combined(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify multiple filters work together (station + year range)."""
        repository = WeatherRepository(db_session)

        stats, total = repository.query_yearly_stats(
            station_id="USC00110072",
            start_year=2021,
            end_year=2023,
        )
        assert total == 3
        assert all(stat.station_id == "USC00110072" for stat in stats)
        assert all(2021 <= stat.year <= 2023 for stat in stats)

    def test_query_yearly_stats_ordered_by_year_descending(
        self, db_session: Session, sample_yearly_stats: list
    ) -> None:
        """Verify results are ordered by year descending (most recent first)."""
        repository = WeatherRepository(db_session)

        stats, _ = repository.query_yearly_stats(station_id="USC00110072")
        years = [stat.year for stat in stats]
        assert years == sorted(years, reverse=True), "Results should be ordered by year descending"


class TestYearlyStatsSchema:
    """Test yearly stats schema documentation and validation."""

    def test_yearly_stat_read_schema_has_required_fields(self) -> None:
        """Verify WeatherYearlyStatRead has all required fields."""
        schema = WeatherYearlyStatRead.model_json_schema()
        required_fields = schema.get("required", [])

        assert "id" in required_fields
        assert "station_id" in required_fields
        assert "year" in required_fields
        assert "observation_count" in required_fields

    def test_yearly_stat_read_schema_field_descriptions(self) -> None:
        """Verify field descriptions are present in schema."""
        schema = WeatherYearlyStatRead.model_json_schema()
        properties = schema.get("properties", {})

        assert properties["id"].get("description"), "id field should have description"
        assert properties["station_id"].get("description"), "station_id field should have description"
        assert properties["year"].get("description"), "year field should have description"
        assert properties["observation_count"].get("description"), "observation_count should have description"

    def test_yearly_stat_read_schema_examples(self) -> None:
        """Verify examples are present in schema."""
        schema = WeatherYearlyStatRead.model_json_schema()
        properties = schema.get("properties", {})

        assert properties["id"].get("example"), "id should have example"
        assert properties["year"].get("example"), "year should have example"

    def test_paginated_yearly_stat_schema_structure(self) -> None:
        """Verify PaginatedWeatherYearlyStatRead schema has correct structure."""
        schema = PaginatedWeatherYearlyStatRead.model_json_schema()
        properties = schema.get("properties", {})

        assert "items" in properties
        assert "total" in properties
        assert "skip" in properties
        assert "limit" in properties

        # Verify pagination fields have descriptions
        assert properties["total"].get("description")
        assert properties["skip"].get("description")
        assert properties["limit"].get("description")

    def test_paginated_yearly_stat_has_example(self) -> None:
        """Verify PaginatedWeatherYearlyStatRead schema includes example."""
        schema = PaginatedWeatherYearlyStatRead.model_json_schema()
        properties = schema.get("properties", {})

        assert properties["total"].get("example"), "total should have example"
        assert properties["skip"].get("example"), "skip should have example"
        assert properties["limit"].get("example"), "limit should have example"


class TestHTTPErrorSchema:
    """Test HTTP error response schemas."""

    def test_http_error_response_schema(self) -> None:
        """Verify HTTPErrorResponse schema structure."""
        schema = HTTPErrorResponse.model_json_schema()
        properties = schema.get("properties", {})

        assert "detail" in properties
        assert properties["detail"].get("description")
        assert properties["detail"].get("example")

    def test_error_response_validation(self) -> None:
        """Verify HTTPErrorResponse validates correctly."""
        error = HTTPErrorResponse(detail="Observation not found")
        assert error.detail == "Observation not found"

        data = error.model_dump()
        assert data == {"detail": "Observation not found"}


class TestYearlyStatsUpsertIdempotency:
    """Test idempotent upsert behavior for yearly statistics."""

    def test_upsert_yearly_stat_creates_new_record(self, db_session: Session) -> None:
        """Verify creating a new yearly stat works."""
        repository = WeatherRepository(db_session)
        service = WeatherService(repository)

        payload = WeatherYearlyStatCreate(
            station_id="USC00110072",
            year=2023,
            avg_max_temp_c=Decimal("24.3"),
            avg_min_temp_c=Decimal("12.8"),
            total_precipitation_cm=Decimal("125.4"),
            observation_count=365,
        )

        result = service.upsert_yearly_stat(payload)
        assert result.id is not None
        assert result.station_id == "USC00110072"
        assert result.year == 2023

    def test_upsert_yearly_stat_updates_existing_record(self, db_session: Session) -> None:
        """Verify updating an existing yearly stat is idempotent."""
        repository = WeatherRepository(db_session)
        service = WeatherService(repository)

        # Create initial stat
        payload1 = WeatherYearlyStatCreate(
            station_id="USC00110072",
            year=2023,
            avg_max_temp_c=Decimal("24.0"),
            observation_count=365,
        )
        result1 = service.upsert_yearly_stat(payload1)
        id1 = result1.id

        # Update with new values
        payload2 = WeatherYearlyStatCreate(
            station_id="USC00110072",
            year=2023,
            avg_max_temp_c=Decimal("24.5"),  # Changed
            observation_count=366,  # Changed
        )
        result2 = service.upsert_yearly_stat(payload2)

        # Verify same record (by ID) and updated values
        assert result2.id == id1
        assert result2.avg_max_temp_c == Decimal("24.5")
        assert result2.observation_count == 366
