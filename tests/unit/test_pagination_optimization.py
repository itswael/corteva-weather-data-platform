"""Tests for pagination and query optimization abstractions.

These tests verify that the new pagination strategies and query analysis
tools work correctly, both with PostgreSQL and SQLite.
"""

import base64
import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, desc
from sqlalchemy.orm import Session

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.pagination import (
    OffsetPaginator,
    KeysetPaginator,
    OffsetPaginationParams,
    KeysetPaginationParams,
)


class TestOffsetPaginator:
    """Test traditional offset-based pagination."""

    def test_offset_paginator_validates_params(self):
        """Test parameter validation."""
        params = OffsetPaginationParams(skip=0, limit=100)
        params.validate(max_limit=1000)  # Should pass

        with pytest.raises(ValueError, match="skip must be >= 0"):
            OffsetPaginationParams(skip=-1, limit=100).validate()

        with pytest.raises(ValueError, match="limit must be between"):
            OffsetPaginationParams(skip=0, limit=0).validate()

        with pytest.raises(ValueError, match="limit must be between"):
            OffsetPaginationParams(skip=0, limit=20001).validate(max_limit=10000)

    def test_offset_paginator_returns_items_and_count(self, db_session: Session):
        """Test offset paginator returns correct results."""
        # Setup test data
        for i in range(10):
            obs = WeatherObservation(
                station_id="TEST001",
                observation_date=date(2020, 1, 1 + i),
                max_temp_c=Decimal("25.0"),
                min_temp_c=Decimal("15.0"),
            )
            db_session.add(obs)
        db_session.commit()

        paginator = OffsetPaginator(db_session)

        def query_callable():
            stmt = select(WeatherObservation).where(
                WeatherObservation.station_id == "TEST001"
            ).order_by(desc(WeatherObservation.observation_date))

            count_stmt = select(func.count()).select_from(WeatherObservation).where(
                WeatherObservation.station_id == "TEST001"
            )
            return stmt, count_stmt, WeatherObservation

        result = paginator.paginate(query_callable, OffsetPaginationParams(skip=0, limit=5))

        assert len(result.items) == 5
        assert result.total_count == 10
        assert result.has_next is True

    def test_offset_paginator_second_page(self, db_session: Session):
        """Test offset paginator handles page 2 correctly."""
        # Setup test data
        for i in range(10):
            obs = WeatherObservation(
                station_id="TEST002",
                observation_date=date(2020, 1, 1 + i),
                max_temp_c=Decimal("25.0"),
                min_temp_c=Decimal("15.0"),
            )
            db_session.add(obs)
        db_session.commit()

        paginator = OffsetPaginator(db_session)

        def query_callable():
            stmt = select(WeatherObservation).where(
                WeatherObservation.station_id == "TEST002"
            ).order_by(desc(WeatherObservation.observation_date))

            count_stmt = select(func.count()).select_from(WeatherObservation).where(
                WeatherObservation.station_id == "TEST002"
            )
            return stmt, count_stmt, WeatherObservation

        # Get first page
        result1 = paginator.paginate(query_callable, OffsetPaginationParams(skip=0, limit=5))
        first_page_ids = {item.id for item in result1.items}

        # Get second page
        result2 = paginator.paginate(query_callable, OffsetPaginationParams(skip=5, limit=5))
        second_page_ids = {item.id for item in result2.items}

        assert first_page_ids.isdisjoint(second_page_ids)  # No overlap
        assert result2.has_next is False  # Last page


class TestKeysetPaginator:
    """Test keyset (cursor-based) pagination."""

    def test_keyset_paginator_validates_params(self):
        """Test parameter validation."""
        params = KeysetPaginationParams(limit=100, cursor=None)
        params.validate(max_limit=1000)  # Should pass

        with pytest.raises(ValueError, match="limit must be between"):
            KeysetPaginationParams(limit=0).validate()

        with pytest.raises(ValueError, match="limit must be between"):
            KeysetPaginationParams(limit=20001).validate(max_limit=10000)

    def test_keyset_paginator_encodes_cursor(self, db_session: Session):
        """Test cursor encoding/decoding."""
        obs = WeatherObservation(
            station_id="TEST003",
            observation_date=date(2020, 1, 15),
            max_temp_c=Decimal("25.0"),
            min_temp_c=Decimal("15.0"),
        )
        db_session.add(obs)
        db_session.commit()

        paginator = KeysetPaginator(
            db_session,
            keyset_columns=[desc(WeatherObservation.observation_date), WeatherObservation.id],
        )

        # Encode cursor
        cursor = paginator._encode_cursor(obs)
        assert isinstance(cursor, str)
        assert len(cursor) > 0

        # Decode cursor
        decoded = paginator._decode_cursor(cursor)
        assert len(decoded) == 2  # Two keyset columns

    def test_keyset_paginator_detects_next_page(self, db_session: Session):
        """Test keyset paginator correctly indicates has_next."""
        # Setup test data
        for i in range(10):
            obs = WeatherObservation(
                station_id="TEST004",
                observation_date=date(2020, 1, 1 + i),
                max_temp_c=Decimal("25.0"),
                min_temp_c=Decimal("15.0"),
            )
            db_session.add(obs)
        db_session.commit()

        paginator = KeysetPaginator(
            db_session,
            keyset_columns=[desc(WeatherObservation.observation_date), WeatherObservation.id],
        )

        def query_callable():
            stmt = select(WeatherObservation).where(
                WeatherObservation.station_id == "TEST004"
            ).order_by(desc(WeatherObservation.observation_date), WeatherObservation.id)
            return stmt, WeatherObservation

        # First page should have next
        result1 = paginator.paginate(
            query_callable,
            KeysetPaginationParams(limit=5, cursor=None),
        )
        assert result1.has_next is True
        assert result1.cursor is not None

        # Last page should not have next
        result2 = paginator.paginate(
            query_callable,
            KeysetPaginationParams(limit=100, cursor=None),  # Get all 10
        )
        assert result2.has_next is False
        assert result2.cursor is None

    def test_keyset_pagination_no_overlap(self, db_session: Session):
        """Test keyset pagination pages have no overlapping items."""
        # Setup test data
        for i in range(10):
            obs = WeatherObservation(
                station_id="TEST005",
                observation_date=date(2020, 1, 1 + i),
                max_temp_c=Decimal("25.0"),
                min_temp_c=Decimal("15.0"),
            )
            db_session.add(obs)
        db_session.commit()

        paginator = KeysetPaginator(
            db_session,
            keyset_columns=[desc(WeatherObservation.observation_date), WeatherObservation.id],
        )

        def query_callable():
            stmt = select(WeatherObservation).where(
                WeatherObservation.station_id == "TEST005"
            ).order_by(desc(WeatherObservation.observation_date), WeatherObservation.id)
            return stmt, WeatherObservation

        # Get first page
        result1 = paginator.paginate(
            query_callable,
            KeysetPaginationParams(limit=3, cursor=None),
        )
        page1_ids = {item.id for item in result1.items}

        # Get second page
        result2 = paginator.paginate(
            query_callable,
            KeysetPaginationParams(limit=3, cursor=result1.cursor),
        )
        page2_ids = {item.id for item in result2.items}

        # Get third page
        result3 = paginator.paginate(
            query_callable,
            KeysetPaginationParams(limit=3, cursor=result2.cursor),
        )
        page3_ids = {item.id for item in result3.items}

        # Verify no overlap
        assert page1_ids.isdisjoint(page2_ids)
        assert page2_ids.isdisjoint(page3_ids)
        assert page1_ids.isdisjoint(page3_ids)

        # Verify total coverage - continue paginating until all records are covered
        all_ids = page1_ids | page2_ids | page3_ids
        
        # If there are more pages, continue fetching
        cursor = result3.cursor
        while result3.has_next and cursor:
            result_next = paginator.paginate(
                query_callable,
                KeysetPaginationParams(limit=3, cursor=cursor),
            )
            page_ids = {item.id for item in result_next.items}
            all_ids.update(page_ids)
            result3 = result_next
            cursor = result3.cursor
        
        assert len(all_ids) == 10  # All records covered

    def test_keyset_pagination_invalid_cursor(self, db_session: Session):
        """Test keyset pagination raises error on invalid cursor."""
        paginator = KeysetPaginator(
            db_session,
            keyset_columns=[desc(WeatherObservation.observation_date)],
        )

        with pytest.raises(ValueError, match="Invalid cursor format"):
            paginator._decode_cursor("invalid_cursor_data")


class TestYearlyStatIndexes:
    """Test that WeatherYearlyStat has correct indexes defined."""

    def test_yearly_stat_has_indexes(self):
        """Verify indexes are defined on the model."""
        indexes = {idx.name for idx in WeatherYearlyStat.__table__.indexes}

        # Check for new indexes
        assert "ix_weather_yearly_stats_station_year" in indexes
        assert "ix_weather_yearly_stats_station" in indexes
        assert "ix_weather_yearly_stats_year" in indexes

    def test_yearly_stat_constraint_preserved(self):
        """Verify unique constraint is preserved."""
        constraints = {c.name for c in WeatherYearlyStat.__table__.constraints}
        assert "uq_weather_yearly_stats_station_year" in constraints


# ========== Integration test markers ==========

@pytest.mark.integration
def test_offset_pagination_with_repository(db_session: Session):
    """Integration test with actual repository."""
    from weather_platform.repositories.weather import SQLAlchemyWeatherRepository

    repo = SQLAlchemyWeatherRepository(db_session)

    # Setup test data
    for i in range(25):
        obs = WeatherObservation(
            station_id="INTEG001",
            observation_date=date(2020, 1, 1 + i),
            max_temp_c=Decimal("25.0"),
            min_temp_c=Decimal("15.0"),
        )
        db_session.add(obs)
    db_session.commit()

    # Test traditional query
    observations, total = repo.query_observations(
        skip=0,
        limit=10,
        station_id="INTEG001",
    )
    assert len(observations) == 10
    assert total == 25


@pytest.mark.integration
def test_keyset_pagination_with_repository(db_session: Session):
    """Integration test keyset pagination with repository."""
    from weather_platform.repositories.weather import SQLAlchemyWeatherRepository

    repo = SQLAlchemyWeatherRepository(db_session)

    # Setup test data
    for i in range(25):
        obs = WeatherObservation(
            station_id="INTEG002",
            observation_date=date(2020, 1, 1 + i),
            max_temp_c=Decimal("25.0"),
            min_temp_c=Decimal("15.0"),
        )
        db_session.add(obs)
    db_session.commit()

    # Test keyset pagination
    result = repo.query_observations_keyset(
        limit=10,
        station_id="INTEG002",
    )
    assert len(result.items) == 10
    assert result.has_next is True
    assert result.cursor is not None
