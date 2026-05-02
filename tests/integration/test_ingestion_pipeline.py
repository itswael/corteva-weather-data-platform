from datetime import date
from decimal import Decimal
from pathlib import Path

from weather_platform.ingestion.ingest_weather_file import (
    WeatherFileIngestor,
    WeatherStationTextFileParser,
)
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.schemas.weather import (
    WeatherObservationCreate,
)
from weather_platform.services.aggregation import WeatherAggregationService
from weather_platform.services.weather import WeatherService


def test_ingestion_pipeline_persists_records_and_aggregates_yearly_stats(
    db_session,
    tmp_path: Path,
) -> None:
    """End-to-end ingestion should parse, transform, persist, and aggregate correctly."""
    weather_file = tmp_path / "USC00110072.txt"
    weather_file.write_text(
        "20240101 00010 00000 00025\n"
        "\n"
        "20240102 -9999 00010 00000\n"
        "20240103 00030 -9999 -9999\n",
        encoding="utf-8",
    )

    repository = SQLAlchemyWeatherRepository(db_session)
    weather_service = WeatherService(repository)
    parser = WeatherStationTextFileParser()
    ingestor = WeatherFileIngestor(service=weather_service, parser=parser)

    summary = ingestor.ingest_file(weather_file)

    assert summary.processed == 3
    assert summary.inserted == 3
    assert summary.skipped_duplicates == 0

    observation = repository.get_observation("USC00110072", date(2024, 1, 2))
    assert observation is not None
    assert observation.max_temp_c is None
    assert observation.min_temp_c == Decimal("1.0")
    assert observation.precipitation_cm == Decimal("0.0")

    aggregation_service = WeatherAggregationService(repository)
    yearly_stat, aggregation_summary = aggregation_service.aggregate_year("USC00110072", 2024)

    assert yearly_stat.station_id == "USC00110072"
    assert yearly_stat.year == 2024
    assert yearly_stat.avg_max_temp_c == Decimal("2.00")
    assert yearly_stat.avg_min_temp_c == Decimal("0.50")
    assert yearly_stat.total_precipitation_cm == Decimal("0.25")
    assert yearly_stat.observation_count == 3
    assert aggregation_summary.observations_processed == 3
    assert aggregation_summary.measurements_available == {
        "max_temp": True,
        "min_temp": True,
        "precipitation": True,
    }


def test_reprocessing_same_file_remains_idempotent(db_session, tmp_path: Path) -> None:
    """Repeated ingestion of the same file should not duplicate rows."""
    weather_file = tmp_path / "USC00110072.txt"
    weather_file.write_text(
        "20240101 00010 00000 00025\n"
        "20240102 00012 00005 00010\n",
        encoding="utf-8",
    )

    repository = SQLAlchemyWeatherRepository(db_session)
    weather_service = WeatherService(repository)
    parser = WeatherStationTextFileParser()
    ingestor = WeatherFileIngestor(service=weather_service, parser=parser)

    first_summary = ingestor.ingest_file(weather_file)
    second_summary = ingestor.ingest_file(weather_file)

    observations, total = repository.query_observations(station_id="USC00110072")

    assert first_summary.processed == 2
    assert second_summary.processed == 2
    assert len(observations) == 2
    assert total == 2


def test_duplicate_single_observation_ingestion_keeps_one_row(db_session) -> None:
    """Ingesting the same observation twice should update in place, not duplicate rows."""
    repository = SQLAlchemyWeatherRepository(db_session)
    weather_service = WeatherService(repository)

    payload = WeatherObservationCreate(
        station_id="USC00110072",
        observation_date=date(2024, 1, 1),
        max_temp_c=Decimal("10.0"),
        min_temp_c=Decimal("0.0"),
        precipitation_cm=Decimal("0.25"),
        source_file="USC00110072.txt",
    )

    first = weather_service.ingest_observation(payload)
    second = weather_service.ingest_observation(payload)

    observations, total = repository.query_observations(station_id="USC00110072")

    assert first.id == second.id
    assert len(observations) == 1
    assert total == 1


def test_stats_rerun_remains_consistent(db_session, tmp_path: Path) -> None:
    """Re-running yearly aggregation should keep the same stat row and values."""
    weather_file = tmp_path / "USC00110072.txt"
    weather_file.write_text(
        "20240101 00010 00000 00025\n"
        "20240102 00020 00010 00050\n",
        encoding="utf-8",
    )

    repository = SQLAlchemyWeatherRepository(db_session)
    weather_service = WeatherService(repository)
    ingestor = WeatherFileIngestor(service=weather_service, parser=WeatherStationTextFileParser())
    ingestor.ingest_file(weather_file)

    aggregation_service = WeatherAggregationService(repository)
    first_stat, first_summary = aggregation_service.aggregate_year("USC00110072", 2024)
    second_stat, second_summary = aggregation_service.aggregate_year("USC00110072", 2024)

    stats = repository.list_yearly_stats("USC00110072")

    assert first_stat.id == second_stat.id
    assert first_stat.avg_max_temp_c == second_stat.avg_max_temp_c
    assert first_stat.avg_min_temp_c == second_stat.avg_min_temp_c
    assert first_stat.total_precipitation_cm == second_stat.total_precipitation_cm
    assert first_summary.observations_processed == second_summary.observations_processed == 2
    assert len(stats) == 1
    assert stats[0].year == 2024
