from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from weather_platform.schemas.weather import WeatherObservationCreate
from weather_platform.ingestion.transformation import (
    WeatherObservationTransformationService,
    build_weather_observation_transformation_service,
)

if TYPE_CHECKING:
    from weather_platform.services.weather import WeatherService


class WeatherFileParseError(ValueError):
    """Raised when a weather station text file cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class WeatherStationRawRecord:
    station_id: str
    observation_date: date
    max_temp_raw: Decimal | None
    min_temp_raw: Decimal | None
    precipitation_raw: Decimal | None
    source_file: str
    line_number: int


class WeatherStationFileParser(ABC):
    """Template method parser for weather station text files.

    The parsing flow is fixed here: load file -> iterate lines -> parse
    -> validate -> transform. Subclasses can override validation and
    transformation hooks without changing the control flow.
    """

    def __init__(
        self,
        *,
        missing_value_sentinel: str = "-9999",
        transformation_service: WeatherObservationTransformationService | None = None,
    ) -> None:
        self.missing_value_sentinel = missing_value_sentinel
        self.transformation_service = transformation_service or build_weather_observation_transformation_service()

    def parse_file(self, file_path: str | Path) -> list[WeatherObservationCreate]:
        path = Path(file_path)
        station_id = self._station_id_from_path(path)
        observations: list[WeatherObservationCreate] = []

        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not self._should_parse_line(raw_line):
                    continue

                raw_record = self._parse_line(
                    raw_line=raw_line,
                    station_id=station_id,
                    source_file=path.name,
                    line_number=line_number,
                )
                self._validate_raw_record(raw_record)
                observations.append(self._transform_raw_record(raw_record))

        return observations

    def _should_parse_line(self, raw_line: str) -> bool:
        stripped = raw_line.strip()
        return bool(stripped) and not stripped.startswith("#")

    def _station_id_from_path(self, file_path: Path) -> str:
        station_id = file_path.stem.strip()
        if not station_id:
            raise WeatherFileParseError(f"Could not derive station id from file name: {file_path}")
        return station_id

    @abstractmethod
    def _parse_line(
        self,
        *,
        raw_line: str,
        station_id: str,
        source_file: str,
        line_number: int,
    ) -> WeatherStationRawRecord:
        raise NotImplementedError

    def _validate_raw_record(self, raw_record: WeatherStationRawRecord) -> None:
        if not raw_record.station_id:
            raise WeatherFileParseError(
                f"Missing station id in {raw_record.source_file} at line {raw_record.line_number}"
            )

    def _transform_raw_record(self, raw_record: WeatherStationRawRecord) -> WeatherObservationCreate:
        return self.transformation_service.transform(
            station_id=raw_record.station_id,
            observation_date=raw_record.observation_date,
            max_temp_raw=raw_record.max_temp_raw,
            min_temp_raw=raw_record.min_temp_raw,
            precipitation_raw=raw_record.precipitation_raw,
            source_file=raw_record.source_file,
        )

    def _parse_measurement_token(
        self,
        token: str,
        *,
        field_name: str,
        source_file: str,
        line_number: int,
    ) -> Decimal | None:
        if token == self.missing_value_sentinel:
            return None

        try:
            return Decimal(token)
        except (InvalidOperation, ValueError) as exc:
            raise WeatherFileParseError(
                f"Invalid {field_name} value in {source_file} at line {line_number}: {token!r}"
            ) from exc


class WeatherStationTextFileParser(WeatherStationFileParser):
    """Parser for the station text files in the workspace."""

    def _parse_line(
        self,
        *,
        raw_line: str,
        station_id: str,
        source_file: str,
        line_number: int,
    ) -> WeatherStationRawRecord:
        parts = raw_line.split()
        if len(parts) != 4:
            raise WeatherFileParseError(
                f"Expected 4 columns in {source_file} at line {line_number}, got {len(parts)}"
            )

        date_token, max_temp_token, min_temp_token, precipitation_token = parts
        try:
            observation_date = datetime.strptime(date_token, "%Y%m%d").date()
        except ValueError as exc:
            raise WeatherFileParseError(
                f"Invalid observation date in {source_file} at line {line_number}: {date_token!r}"
            ) from exc

        return WeatherStationRawRecord(
            station_id=station_id,
            observation_date=observation_date,
            max_temp_raw=self._parse_measurement_token(
                max_temp_token,
                field_name="max_temp_c",
                source_file=source_file,
                line_number=line_number,
            ),
            min_temp_raw=self._parse_measurement_token(
                min_temp_token,
                field_name="min_temp_c",
                source_file=source_file,
                line_number=line_number,
            ),
            precipitation_raw=self._parse_measurement_token(
                precipitation_token,
                field_name="precipitation_cm",
                source_file=source_file,
                line_number=line_number,
            ),
            source_file=source_file,
            line_number=line_number,
        )


class WeatherFileIngestor:
    def __init__(
        self,
        service: "WeatherService",
        parser: WeatherStationFileParser | None = None,
    ) -> None:
        self.service = service
        self.parser = parser or WeatherStationTextFileParser()

    def ingest(self, records: Iterable[WeatherObservationCreate]):
        return [self.service.ingest_observation(record) for record in records]

    def ingest_file(self, file_path: str | Path):
        records = self.parser.parse_file(file_path)
        return self.ingest(records)
