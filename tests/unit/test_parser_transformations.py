from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from weather_platform.ingestion.ingest_weather_file import (
    WeatherFileIngestSummary,
    WeatherFileIngestor,
    WeatherFileParseError,
    WeatherStationTextFileParser,
)


def test_parse_file_transforms_missing_values_and_skips_blank_lines(tmp_path: Path) -> None:
    """Parser should convert sentinel values to None and ignore blank lines."""
    file_path = tmp_path / "USC00110072.txt"
    file_path.write_text(
        "\n"
        "20240101 00010 -9999 00000\n"
        "\n"
        "20240102 -9999 00032 00015\n",
        encoding="utf-8",
    )

    parser = WeatherStationTextFileParser()
    records = parser.parse_file(file_path)

    assert len(records) == 2

    first = records[0]
    assert first.station_id == "USC00110072"
    assert first.observation_date == date(2024, 1, 1)
    assert first.max_temp_c == Decimal("1.0")
    assert first.min_temp_c is None
    assert first.precipitation_cm == Decimal("0.0")
    assert first.source_file == "USC00110072.txt"

    second = records[1]
    assert second.station_id == "USC00110072"
    assert second.observation_date == date(2024, 1, 2)
    assert second.max_temp_c is None
    assert second.min_temp_c == Decimal("3.2")
    assert second.precipitation_cm == Decimal("0.15")


def test_parse_file_raises_parse_error_for_short_record(tmp_path: Path) -> None:
    """Parser should reject malformed records with too few columns."""
    file_path = tmp_path / "USC00110072.txt"
    file_path.write_text("20240101 00010 -9999\n", encoding="utf-8")

    parser = WeatherStationTextFileParser()

    with pytest.raises(WeatherFileParseError, match="Invalid weather record on line 1"):
        parser.parse_file(file_path)


def test_parse_file_wraps_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parser should convert file IO failures into WeatherFileParseError."""
    file_path = Path("USC00110072.txt")

    def raise_oserror(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "open", raise_oserror)

    parser = WeatherStationTextFileParser()

    with pytest.raises(WeatherFileParseError, match="Unable to read weather file"):
        parser.parse_file(file_path)


def test_ingest_file_uses_injected_parser_and_service(tmp_path: Path) -> None:
    """Ingestor should use injected parser and service dependencies."""
    file_path = tmp_path / "USC00110072.txt"
    file_path.write_text(
        "20240101 00010 00005 00000\n"
        "20240102 00012 -9999 00010\n",
        encoding="utf-8",
    )

    parser = WeatherStationTextFileParser()
    service = Mock()
    service.ingest_observation.side_effect = lambda record: record

    ingestor = WeatherFileIngestor(service=service, parser=parser)
    summary = ingestor.ingest_file(file_path)

    assert summary == WeatherFileIngestSummary(processed=2, inserted=2, skipped_duplicates=0)
    assert service.ingest_observation.call_count == 2
    first_call = service.ingest_observation.call_args_list[0].args[0]
    assert first_call.station_id == "USC00110072"
    assert first_call.max_temp_c == Decimal("1.0")


def test_ingest_handles_empty_parser_output() -> None:
    """Ingestor should return a zero-count summary when parser returns no records."""
    parser = Mock()
    parser.parse_file.return_value = []
    service = Mock()

    ingestor = WeatherFileIngestor(service=service, parser=parser)
    summary = ingestor.ingest_file(Path("USC00110072.txt"))

    assert summary.processed == 0
    assert summary.inserted == 0
    assert summary.skipped_duplicates == 0
    service.ingest_observation.assert_not_called()
