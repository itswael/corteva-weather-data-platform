from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from weather_platform.ingestion import WeatherFileIngestor
from weather_platform.schemas.weather import WeatherObservationCreate


@dataclass(frozen=True, slots=True)
class BatchSummary:
    processed: int
    inserted: int
    skipped_duplicates: int
    duration_ms: int


class FakeService:
    def __init__(self, summary: BatchSummary) -> None:
        self.summary = summary
        self.calls: list[list[WeatherObservationCreate]] = []

    def ingest_observations(self, observations):
        self.calls.append(list(observations))
        return self.summary


class FakeParser:
    def __init__(self, observations: list[WeatherObservationCreate]) -> None:
        self.observations = observations
        self.paths: list[str] = []

    def parse_file(self, file_path):
        self.paths.append(str(file_path))
        return self.observations


def _build_observation(observation_date: date, precipitation_cm: Decimal | None) -> WeatherObservationCreate:
    return WeatherObservationCreate(
        station_id="USC00110072",
        observation_date=observation_date,
        max_temp_c=Decimal("-2.2"),
        min_temp_c=Decimal("-12.8"),
        precipitation_cm=precipitation_cm,
        source_file="USC00110072.txt",
    )


def test_file_ingestor_emits_structured_summary(monkeypatch, tmp_path) -> None:
    summary = BatchSummary(processed=2, inserted=1, skipped_duplicates=1, duration_ms=7)
    service = FakeService(summary)
    parser = FakeParser(
        [
            _build_observation(date(1985, 1, 1), Decimal("0.94")),
            _build_observation(date(1985, 1, 2), None),
        ]
    )
    ingestor = WeatherFileIngestor(service=service, parser=parser)
    file_path = tmp_path / "USC00110072.txt"
    file_path.write_text("ignored by fake parser", encoding="utf-8")

    captured: list[dict[str, object]] = []

    def fake_log_structured_event(event_name: str, **fields: object) -> None:
        captured.append({"event": event_name, **fields})

    monkeypatch.setattr("weather_platform.ingestion.ingest_weather_file.log_structured_event", fake_log_structured_event)

    returned_summary = ingestor.ingest_file(file_path)

    assert returned_summary == summary
    assert parser.paths == [str(file_path)]
    assert service.calls == [[
        _build_observation(date(1985, 1, 1), Decimal("0.94")),
        _build_observation(date(1985, 1, 2), None),
    ]]
    assert captured == [
        {
            "event": "weather_file_ingestion_completed",
            "source_file": "USC00110072.txt",
            "processed": 2,
            "inserted": 1,
            "skipped_duplicates": 1,
            "duration_ms": 7,
        }
    ]
