from datetime import date
from decimal import Decimal

import pytest

from weather_platform.ingestion import WeatherFileParseError, WeatherStationTextFileParser


def test_weather_station_text_parser_converts_missing_values_and_scales(tmp_path) -> None:
    file_path = tmp_path / "USC00110072.txt"
    file_path.write_text(
        "19850101  -22  -128   94\n"
        "19850201  -83 -9999    0\n",
        encoding="utf-8",
    )

    parser = WeatherStationTextFileParser()
    observations = parser.parse_file(file_path)

    assert len(observations) == 2
    assert observations[0].station_id == "USC00110072"
    assert observations[0].observation_date == date(1985, 1, 1)
    assert observations[0].max_temp_c == Decimal("-2.20")
    assert observations[0].min_temp_c == Decimal("-12.80")
    assert observations[0].precipitation_cm == Decimal("0.94")
    assert observations[0].source_file == "USC00110072.txt"

    assert observations[1].min_temp_c is None
    assert observations[1].precipitation_cm == Decimal("0.00")


def test_weather_station_text_parser_rejects_malformed_lines(tmp_path) -> None:
    file_path = tmp_path / "USC00110072.txt"
    file_path.write_text("19850101  -22  -128\n", encoding="utf-8")

    parser = WeatherStationTextFileParser()

    with pytest.raises(WeatherFileParseError, match="Expected 4 columns"):
        parser.parse_file(file_path)
