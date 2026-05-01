from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from sqlalchemy.dialects import sqlite

from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.schemas.weather import WeatherYearlyStatCreate


def test_upsert_yearly_stat_uses_conflict_update_for_reprocessing() -> None:
    """Ensure yearly-stat persistence stays idempotent on repeated writes."""
    session = Mock()
    session.get_bind.return_value = Mock(dialect=Mock(name="sqlite"))

    persisted_stat = WeatherYearlyStat(
        id=1,
        station_id="USC00110072",
        year=2023,
        avg_max_temp_c=Decimal("18.25"),
        avg_min_temp_c=Decimal("7.75"),
        total_precipitation_cm=Decimal("42.00"),
        observation_count=365,
        created_at=datetime.now(),
    )
    session.scalars.return_value.one.return_value = persisted_stat

    repository = SQLAlchemyWeatherRepository(session)
    payload = WeatherYearlyStatCreate(
        station_id="USC00110072",
        year=2023,
        avg_max_temp_c=Decimal("18.25"),
        avg_min_temp_c=Decimal("7.75"),
        total_precipitation_cm=Decimal("42.00"),
        observation_count=365,
    )

    result = repository.upsert_yearly_stat(payload)

    session.execute.assert_called_once()
    statement = session.execute.call_args.args[0]
    compiled_sql = str(statement.compile(dialect=sqlite.dialect()))

    assert "ON CONFLICT" in compiled_sql
    assert "station_id" in compiled_sql
    assert "year" in compiled_sql
    assert result is persisted_stat
    session.commit.assert_called_once()
