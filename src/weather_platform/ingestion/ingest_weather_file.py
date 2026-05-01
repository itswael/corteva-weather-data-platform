"""Weather file parsing and ingestion orchestration.

This module provides the parsing logic (template method pattern) and
ingestion orchestration for converting weather station text files into
database records with proper validation and unit conversion.
"""
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
from weather_platform.utils.structured_logging import log_structured_event

if TYPE_CHECKING:
    from weather_platform.services.weather import WeatherService


class WeatherFileParseError(ValueError):
    """Raised when a weather station text file cannot be parsed safely.
    
    This exception indicates unrecoverable parse errors such as:
    - Missing or invalid station ID
    - Invalid date format
    - Invalid column counts
    """


@dataclass(frozen=True, slots=True)
class WeatherStationRawRecord:
    """Raw measurement record parsed directly from file (before unit conversion).
    
    This intermediate representation holds raw values before unit conversion
    and validation. Using slots and frozen reduces memory usage for large
    batches of observations.
    
    Attributes:
        station_id: NOAA station identifier from filename
        observation_date: Parsed observation date
        max_temp_raw: Raw max temperature (tenths of Celsius or None)
        min_temp_raw: Raw min temperature (tenths of Celsius or None)
        precipitation_raw: Raw precipitation (tenths of mm or None)
        source_file: Filename for audit tracking
        line_number: Line number in source file for error reporting
    """
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
        """Check if line should be parsed (skip comments and empty lines).
        
        Args:
            raw_line: Line from input file
            
        Returns:
            bool: True if line should be parsed, False to skip
        """
        stripped = raw_line.strip()
        # Skip empty lines and lines starting with '#' (comments)
        return bool(stripped) and not stripped.startswith("#")

    def _station_id_from_path(self, file_path: Path) -> str:
        """Extract station ID from filename (stem without extension).
        
        Args:
            file_path: Path object
            
        Returns:
            str: Station ID from filename
            
        Raises:
            WeatherFileParseError: If filename stem is empty or invalid
        """
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
        """Parse a single line into raw record (implemented by subclass).
        
        Args:
            raw_line: Line from input file
            station_id: Station ID extracted from filename
            source_file: Filename for audit tracking
            line_number: Line number in source file for error messages
            
        Returns:
            WeatherStationRawRecord: Parsed raw record with measurements
            
        Raises:
            WeatherFileParseError: If line cannot be parsed
        """
        raise NotImplementedError

    def _validate_raw_record(self, raw_record: WeatherStationRawRecord) -> None:
        """Validate raw record after parsing.
       Concrete parser for whitespace-delimited weather station text files.
    
    Expected file format (whitespace-delimited):
        YYYYMMDD max_temp min_temp precipitation
        
    Where:
    - YYYYMMDD: Date in format YYYYMMDD
    - max_temp: Maximum temperature in tenths of Celsius (e.g., 120 = 12.0°C)
    - min_temp: Minimum temperature in tenths of Celsius
    - precipitation: Precipitation in tenths of millimeters
    - Missing values represented as -9999
    """

    def _parse_line(
        self,
        *,
        raw_line: str,
        station_id: str,
        source_file: str,
        line_number: int,
    ) -> WeatherStationRawRecord:
        """Parse whitespace-delimited line.
        
        Args:
            raw_line: Line from input file (whitespace-delimited)
            station_id: Station ID from filename
            source_file: Filename for error messages
            line_number: Line number for error messages
            
        Returns:
            WeatherStationRawRecord: Parsed measurement data
            
        Raises:
            WeatherFileParseError: If line format is invalid
        """
        # Split by whitespace, expect exactly 4 columns
        parts = raw_line.split()
        if len(parts) != 4:
            raise WeatherFileParseError(
                f"Expected 4 columns in {source_file} at line {line_number}, got {len(parts)}"
            )

        # Unpack: date, max_temp, min_temp, precipitation
        date_token, max_temp_token, min_temp_token, precipitation_token = parts
        
        # Parse date in YYYYMMDD format
        try:
            observation_date = datetime.strptime(date_token, "%Y%m%d").date()
        except ValueError as exc:
            raise WeatherFileParseError(
                f"Invalid observation date in {source_file} at line {line_number}: {date_token!r}"
            ) from exc

        # Parse each measurement, converting sentinel values to None
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
    """Orchestrates file parsing and ingestion into the database.
    
    Coordinates between the parser (extracts raw data from files) and
    the service layer (handles business logic and persistence).
    
    Attributes:
        service: WeatherService instance for data persistence
        parser: WeatherStationFileParser instance for parsing
    """
    
    def __init__(
        self,
        service: "WeatherService",
        parser: WeatherStationFileParser | None = None,
    ) -> None:
        """Initialize ingestor with service and optional parser.
        
        Args:
            service: WeatherService instance for persistence
            parser: Parser instance (defaults to WeatherStationTextFileParser)
        """
        self.service = service
        self.parser = parser or WeatherStationTextFileParser()

    def ingest(self, records: Iterable[WeatherObservationCreate]):
        """Ingest parsed records through the service layer.
        
        Args:
            records: Iterable of parsed observation schemas
            
        Returns:
            IngestionSummary: Metrics about processed/inserted/skipped records
        """
        return self.service.ingest_observations(records)

    def ingest_file(self, file_path: str | Path):
        """Orchestrate full file ingestion workflow.
        
        Parses the file, ingests records, emits structured log events.
        
        Args:
            file_path: Path to weather station data file
            
        Returns:
            IngestionSummary: Metrics about ingestion (processed, inserted, etc.)
            
        Raises:
            WeatherFileParseError: If file cannot be parsed
            
        Implementation:
            1. Parse the file to extract observations
            2. Ingest through service layer (idempotent, handles duplicates)
            3. Emit structured log event with summary metrics
            4. Return ingestion summary
        """
        path = Path(file_path)
        
        # Parse file into observations
        records = self.parser.parse_file(path)
        
        # Ingest through service layer (handles duplicates via ON CONFLICT DO NOTHING)
        summary = self.ingest(records)
        
        # Emit structured event for monitoring/logging systems


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
        return self.service.ingest_observations(records)

    def ingest_file(self, file_path: str | Path):
        path = Path(file_path)
        records = self.parser.parse_file(path)
        summary = self.ingest(records)
        log_structured_event(
            "weather_file_ingestion_completed",
            source_file=path.name,
            processed=summary.processed,
            inserted=summary.inserted,
            skipped_duplicates=summary.skipped_duplicates,
            duration_ms=summary.duration_ms,
        )
        return summary
