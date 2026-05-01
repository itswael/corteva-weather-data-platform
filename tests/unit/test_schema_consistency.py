from pathlib import Path

from weather_platform.models import Base
from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat


def test_orm_schema_matches_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"weather_observations", "weather_yearly_stats"}

    observation_table = WeatherObservation.__table__
    yearly_table = WeatherYearlyStat.__table__

    assert observation_table.name == "weather_observations"
    assert yearly_table.name == "weather_yearly_stats"

    assert [column.name for column in observation_table.columns] == [
        "id",
        "created_at",
        "station_id",
        "observation_date",
        "max_temp_c",
        "min_temp_c",
        "precipitation_cm",
        "source_file",
    ]
    assert [column.name for column in yearly_table.columns] == [
        "id",
        "created_at",
        "station_id",
        "year",
        "avg_max_temp_c",
        "avg_min_temp_c",
        "total_precipitation_cm",
        "observation_count",
    ]

    observation_constraint_names = {
        constraint.name for constraint in observation_table.constraints if constraint.name
    }
    yearly_constraint_names = {constraint.name for constraint in yearly_table.constraints if constraint.name}
    observation_index_names = {index.name for index in observation_table.indexes}

    assert "uq_weather_observations_station_date" in observation_constraint_names
    assert "uq_weather_yearly_stats_station_year" in yearly_constraint_names
    assert observation_index_names == {
        "ix_weather_observations_station_date",
        "ix_weather_observations_observation_date",
    }


def test_alembic_revision_contains_both_weather_tables() -> None:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "versions"
        / "20260430_0001_create_weather_tables.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "weather_observations" in migration_text
    assert "weather_yearly_stats" in migration_text
    assert "uq_weather_observations_station_date" in migration_text
    assert "uq_weather_yearly_stats_station_year" in migration_text
    assert "def downgrade() -> None:" in migration_text
    assert "op.drop_table(\"weather_yearly_stats\")" in migration_text
    assert "op.drop_table(\"weather_observations\")" in migration_text
