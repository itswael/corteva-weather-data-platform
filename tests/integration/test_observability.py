from pathlib import Path

from weather_platform.ingestion.ingest_weather_file import (
    WeatherFileIngestor,
    WeatherStationTextFileParser,
)
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService


def test_request_correlation_id_is_echoed_on_weather_endpoint(client) -> None:
    """Middleware should echo a caller-provided request correlation id."""
    request_id = "test-request-id-123"
    response = client.post(
        "/api/v1/weather/observations",
        headers={"X-Request-ID": request_id},
        json={
            "station_id": "USC00110072",
            "observation_date": "2024-05-01",
            "max_temp_c": "26.0",
            "min_temp_c": "13.0",
            "precipitation_cm": "0.0",
            "source_file": "sample.txt",
        },
    )

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["station_id"] == "USC00110072"


def test_health_live_returns_request_metadata(client) -> None:
    """Liveness checks should return a request id and live metrics snapshot."""
    request_id = "health-live-request-001"
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": request_id})

    payload = response.json()

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert payload["status"] == "ok"
    assert payload["request_id"] == request_id
    assert payload["database_status"] is None
    assert payload["request_metrics"]["total_requests"] >= 1
    assert payload["ingestion_metrics"]["files_processed"] == 0


def test_health_ready_reports_database_and_ingestion_metrics(
    client,
    db_session,
    tmp_path: Path,
) -> None:
    """Readiness checks should expose database status and ingestion metrics."""
    weather_file = tmp_path / "USC00110072.txt"
    weather_file.write_text(
        "20240501 00010 00000 00025\n"
        "20240502 00020 00010 00050\n",
        encoding="utf-8",
    )

    repository = SQLAlchemyWeatherRepository(db_session)
    weather_service = WeatherService(repository)
    ingestor = WeatherFileIngestor(service=weather_service, parser=WeatherStationTextFileParser())
    summary = ingestor.ingest_file(weather_file)

    assert summary.processed == 2

    response = client.get("/api/v1/health/ready")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["database_status"] == "ok"
    assert payload["ingestion_metrics"]["files_processed"] == 1
    assert payload["ingestion_metrics"]["records_processed"] == 2
    assert payload["ingestion_metrics"]["records_inserted"] == 2
    assert payload["ingestion_metrics"]["parse_errors"] == 0
