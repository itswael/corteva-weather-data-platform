from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from weather_platform.schemas.weather import WeatherObservationCreate
from weather_platform.services.weather import WeatherService


class WeatherFileParseError(ValueError):
    pass


class WeatherStationTextFileParser:
    def parse_file(self, file_path: Path) -> list[WeatherObservationCreate]:
        try:
            station_id = file_path.stem
            records: list[WeatherObservationCreate] = []

            with file_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue

                    parts = stripped.split()
                    if len(parts) < 4:
                        raise WeatherFileParseError(
                            f"Invalid weather record on line {line_number}: {line.rstrip()}"
                        )

                    observation_date = date.fromisoformat(
                        f"{parts[0][0:4]}-{parts[0][4:6]}-{parts[0][6:8]}"
                    )
                    max_temp_c = _parse_measurement(parts[1], scale=Decimal("10"))
                    min_temp_c = _parse_measurement(parts[2], scale=Decimal("10"))
                    precipitation_cm = _parse_measurement(parts[3], scale=Decimal("100"))

                    records.append(
                        WeatherObservationCreate(
                            station_id=station_id,
                            observation_date=observation_date,
                            max_temp_c=max_temp_c,
                            min_temp_c=min_temp_c,
                            precipitation_cm=precipitation_cm,
                            source_file=file_path.name,
                        )
                    )

            return records
        except OSError as exc:
            raise WeatherFileParseError(f"Unable to read weather file {file_path}: {exc}") from exc
        except ValidationError as exc:
            raise WeatherFileParseError(str(exc)) from exc


def _parse_measurement(raw_value: str, scale: Decimal) -> Decimal | None:
    value = int(raw_value)
    if value <= -9999:
        return None
    return Decimal(value) / scale


@dataclass(frozen=True)
class WeatherFileIngestSummary:
    processed: int
    inserted: int
    skipped_duplicates: int


class WeatherFileIngestor:
    def __init__(self, service: WeatherService, parser: WeatherStationTextFileParser) -> None:
        self.service = service
        self.parser = parser

    def ingest(self, records: Iterable[WeatherObservationCreate]):
        return [self.service.ingest_observation(record) for record in records]

    def ingest_file(self, file_path: Path) -> WeatherFileIngestSummary:
        records = self.parser.parse_file(file_path)
        observations = self.ingest(records)
        processed = len(records)
        inserted = len(observations)
        return WeatherFileIngestSummary(
            processed=processed,
            inserted=inserted,
            skipped_duplicates=0,
        )
