"""Add performance indexes to weather_yearly_stats and observation date range queries

Revision ID: 20260502_0001
Revises: 20260430_0001
Create Date: 2026-05-02 00:00:00.000000

This migration adds missing indexes to improve query performance:
- (station_id, year) composite index for filtering yearly stats
- (observation_date DESC, station_id) index for time-series queries
- (station_id) index for station-only queries
- (station_id, observation_date DESC) for efficient keyset-based pagination
"""

from alembic import op
import sqlalchemy as sa

revision = "20260502_0001"
down_revision = "20260430_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Index for yearly stats filtering by station and year (covers query_yearly_stats)
    op.create_index(
        "ix_weather_yearly_stats_station_year",
        "weather_yearly_stats",
        ["station_id", "year"],
        unique=False,
    )

    # Index for yearly stats filtering by station only
    op.create_index(
        "ix_weather_yearly_stats_station",
        "weather_yearly_stats",
        ["station_id"],
        unique=False,
    )

    # Index for yearly stats filtering by year only
    op.create_index(
        "ix_weather_yearly_stats_year",
        "weather_yearly_stats",
        ["year"],
        unique=False,
    )

    # Index for observations: descending date with station for keyset pagination
    # Descending date matches ORDER BY observation_date DESC in typical queries
    op.create_index(
        "ix_weather_observations_station_date_desc",
        "weather_observations",
        [
            sa.desc(sa.column("observation_date")),
            "station_id",
        ],
        unique=False,
    )

    # Index for observations: descending date only for non-filtered queries
    op.create_index(
        "ix_weather_observations_date_desc",
        "weather_observations",
        [sa.desc(sa.column("observation_date"))],
        unique=False,
    )

    # Index for station-only filtering
    op.create_index(
        "ix_weather_observations_station",
        "weather_observations",
        ["station_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_weather_observations_station", table_name="weather_observations")
    op.drop_index("ix_weather_observations_date_desc", table_name="weather_observations")
    op.drop_index("ix_weather_observations_station_date_desc", table_name="weather_observations")
    op.drop_index("ix_weather_yearly_stats_year", table_name="weather_yearly_stats")
    op.drop_index("ix_weather_yearly_stats_station", table_name="weather_yearly_stats")
    op.drop_index("ix_weather_yearly_stats_station_year", table_name="weather_yearly_stats")
