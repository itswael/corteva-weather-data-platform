from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from pydantic import ValidationError

from weather_platform.utils.observability import get_application_metrics
from weather_platform.utils.structured_logging import log_structured_event
from weather_platform.schemas.weather import WeatherObservationCreate
from weather_platform.services.weather import WeatherService


class WeatherFileParseError(ValueError):
    pass


MAX_WEATHER_FILE_BYTES = 10 * 1024 * 1024
STATION_ID_PATTERN = r"^[A-Z0-9]{5,20}$"


class WeatherStationTextFileParser:
    def parse_file(self, file_path: Path) -> list[WeatherObservationCreate]:
        try:
            station_id = file_path.stem.upper().strip()
            if not re.fullmatch(STATION_ID_PATTERN, station_id):
                raise WeatherFileParseError(
                    f"Invalid station identifier derived from filename: {file_path.name}"
                )

            if file_path.suffix.lower() != ".txt":
                raise WeatherFileParseError("Weather input file must use .txt extension")

            file_size = file_path.stat().st_size
            if file_size > MAX_WEATHER_FILE_BYTES:
                raise WeatherFileParseError(
                    f"Weather input file exceeds size limit ({MAX_WEATHER_FILE_BYTES} bytes)"
                )

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

                    if len(parts[0]) != 8 or not parts[0].isdigit():
                        raise WeatherFileParseError(
                            f"Invalid date token on line {line_number}: {parts[0]}"
                        )

                    try:
                        observation_date = date.fromisoformat(
                            f"{parts[0][0:4]}-{parts[0][4:6]}-{parts[0][6:8]}"
                        )
                        max_temp_c = _parse_measurement(parts[1], scale=Decimal("10"))
                        min_temp_c = _parse_measurement(parts[2], scale=Decimal("10"))
                        precipitation_cm = _parse_measurement(parts[3], scale=Decimal("100"))
                    except ValueError as exc:
                        raise WeatherFileParseError(
                            f"Invalid numeric/date value on line {line_number}: {line.rstrip()}"
                        ) from exc

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
        # Use service batch ingestion when available for performance
        if hasattr(self.service, "ingest_observations_batch"):
            # service expects a list
            return self.service.ingest_observations_batch(list(records))

        return [self.service.ingest_observation(record) for record in records]

    def ingest_file(self, file_path: Path) -> WeatherFileIngestSummary:
        metrics = get_application_metrics()
        log_structured_event("ingestion.file.started", file=file_path.name)

        try:
            records = self.parser.parse_file(file_path)
        except WeatherFileParseError:
            metrics.record_ingestion(files_failed=1, parse_errors=1)
            log_structured_event("ingestion.file.failed", file=file_path.name)
            raise

        inserted = self.ingest(records)
        processed = len(records)
        summary = WeatherFileIngestSummary(
            processed=processed,
            inserted=inserted,
            skipped_duplicates=0,
        )
        metrics.record_ingestion(
            files_processed=1,
            records_processed=processed,
            records_inserted=inserted,
            duplicate_records=summary.skipped_duplicates,
        )
        log_structured_event(
            "ingestion.file.completed",
            file=file_path.name,
            processed=summary.processed,
            inserted=summary.inserted,
            skipped_duplicates=summary.skipped_duplicates,
        )
        return summary
