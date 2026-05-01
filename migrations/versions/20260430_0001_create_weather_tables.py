"""Create weather observation and yearly stats tables

Revision ID: 20260430_0001
Revises:
Create Date: 2026-04-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260430_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.String(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("max_temp_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("min_temp_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("precipitation_cm", sa.Numeric(8, 2), nullable=True),
        sa.Column("source_file", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "station_id",
            "observation_date",
            name="uq_weather_observations_station_date",
        ),
    )
    op.create_index(
        "ix_weather_observations_station_date",
        "weather_observations",
        ["station_id", "observation_date"],
        unique=False,
    )
    op.create_index(
        "ix_weather_observations_observation_date",
        "weather_observations",
        ["observation_date"],
        unique=False,
    )

    op.create_table(
        "weather_yearly_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("avg_max_temp_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("avg_min_temp_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("total_precipitation_cm", sa.Numeric(10, 2), nullable=True),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "station_id",
            "year",
            name="uq_weather_yearly_stats_station_year",
        ),
    )


def downgrade() -> None:
    op.drop_table("weather_yearly_stats")
    op.drop_index("ix_weather_observations_observation_date", table_name="weather_observations")
    op.drop_index("ix_weather_observations_station_date", table_name="weather_observations")
    op.drop_table("weather_observations")
