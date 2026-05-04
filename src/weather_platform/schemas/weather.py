from datetime import date, datetime
from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATION_ID_PATTERN = r"^[A-Z0-9_]{5,20}$"
SOURCE_FILE_PATTERN = r"^[A-Za-z0-9._-]{1,255}$"


class WeatherObservationCreate(BaseModel):
    """Request model for creating or updating weather observations.
    
    All temperature and precipitation values are optional to support sparse data.
    Missing values should be omitted from the request body (not set to null).
    """
    station_id: str = Field(
        min_length=1,
        max_length=20,
        pattern=STATION_ID_PATTERN,
        description="NOAA station identifier (e.g., USC00110072)",
        example="USC00110072"
    )
    observation_date: date = Field(
        description="Date of observation in YYYY-MM-DD format",
        example="2023-06-15"
    )
    max_temp_c: Decimal | None = Field(
        default=None,
        ge=Decimal("-99.99"),
        le=Decimal("99.99"),
        max_digits=5,
        decimal_places=2,
        description="Maximum temperature in Celsius (-99.99 to 99.99). Null or omitted if not measured.",
        example="28.5"
    )
    min_temp_c: Decimal | None = Field(
        default=None,
        ge=Decimal("-99.99"),
        le=Decimal("99.99"),
        max_digits=5,
        decimal_places=2,
        description="Minimum temperature in Celsius (-99.99 to 99.99). Null or omitted if not measured.",
        example="16.2"
    )
    precipitation_cm: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        le=Decimal("999.99"),
        max_digits=8,
        decimal_places=2,
        description="Total precipitation in centimeters (0-999.99). Null or omitted if not measured.",
        example="0.0"
    )
    source_file: str | None = Field(
        default=None,
        max_length=255,
        description="Source file name or identifier for data lineage tracking",
        example="USC00110072.txt"
    )

    @field_validator("station_id")
    @classmethod
    def validate_station_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(STATION_ID_PATTERN, normalized):
            raise ValueError("station_id must be 5-20 uppercase alphanumeric characters")
        return normalized

    @field_validator("source_file")
    @classmethod
    def validate_source_file(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if "/" in normalized or "\\" in normalized or ".." in normalized:
            raise ValueError("source_file must be a safe filename without path segments")
        if not re.fullmatch(SOURCE_FILE_PATTERN, normalized):
            raise ValueError("source_file contains unsupported characters")
        return normalized


class WeatherObservationRead(WeatherObservationCreate):
    """Response model for weather observations.
    
    Includes all fields from WeatherObservationCreate plus system-generated fields
    (id, created_at). Maps from ORM models using from_attributes configuration.
    """
    id: int = Field(
        description="Unique observation identifier",
        example=1
    )
    created_at: datetime = Field(
        description="Timestamp when observation was recorded (ISO 8601 UTC)",
        example="2024-01-15T10:30:00"
    )

    model_config = ConfigDict(from_attributes=True)


class WeatherYearlyStatCreate(BaseModel):
    """Request model for creating or updating yearly weather statistics.
    
    Aggregated annual statistics for a weather station. All aggregate values are
    optional to support sparse or incomplete data years.
    """
    station_id: str = Field(
        min_length=1,
        max_length=20,
        pattern=STATION_ID_PATTERN,
        description="NOAA station identifier (e.g., USC00110072)",
        example="USC00110072"
    )
    year: int = Field(
        ge=1800,
        le=3000,
        description="Calendar year for which statistics are aggregated",
        example=2023
    )
    avg_max_temp_c: Decimal | None = Field(
        default=None,
        ge=Decimal("-99.99"),
        le=Decimal("99.99"),
        max_digits=5,
        decimal_places=2,
        description="Average of daily maximum temperatures in Celsius. Null if no data available.",
        example="24.3"
    )
    avg_min_temp_c: Decimal | None = Field(
        default=None,
        ge=Decimal("-99.99"),
        le=Decimal("99.99"),
        max_digits=5,
        decimal_places=2,
        description="Average of daily minimum temperatures in Celsius. Null if no data available.",
        example="12.8"
    )
    total_precipitation_cm: Decimal | None = Field(
        default=None,
        ge=Decimal("0.00"),
        le=Decimal("9999.99"),
        max_digits=10,
        decimal_places=2,
        description="Total annual precipitation in centimeters. Null if no data available.",
        example="125.4"
    )
    observation_count: int = Field(
        ge=0,
        le=1000000,
        description="Number of observations included in year aggregate",
        example=365
    )

    @field_validator("station_id")
    @classmethod
    def validate_station_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(STATION_ID_PATTERN, normalized):
            raise ValueError("station_id must be 5-20 uppercase alphanumeric characters")
        return normalized


class WeatherYearlyStatRead(WeatherYearlyStatCreate):
    """Response model for yearly weather statistics.
    
    Includes all fields from WeatherYearlyStatCreate plus system-generated fields
    (id, created_at). Maps from ORM models using from_attributes configuration.
    """
    id: int = Field(
        description="Unique yearly statistic record identifier",
        example=1
    )
    created_at: datetime = Field(
        description="Timestamp when statistic was recorded (ISO 8601 UTC)",
        example="2024-01-01T00:00:00"
    )

    model_config = ConfigDict(from_attributes=True)


class HTTPErrorResponse(BaseModel):
    """Standard HTTP error response format.
    
    Follows RFC 7807 error response conventions for consistent error handling.
    """
    detail: str = Field(
        description="Human-readable error description",
        example="Observation not found"
    )


class ValidationErrorDetail(BaseModel):
    """Details of a single validation error."""
    loc: list[str | int] = Field(
        description="Location path to the invalid field (e.g., ['station_id'])",
        example=["station_id"]
    )
    msg: str = Field(
        description="Validation error message",
        example="String should have at least 1 character"
    )
    type: str = Field(
        description="Error type code",
        example="string_too_short"
    )


class ValidationErrorResponse(BaseModel):
    """Response model for validation errors (HTTP 422)."""
    detail: list[ValidationErrorDetail] = Field(
        description="List of validation errors for each invalid field",
        example=[{
            "loc": ["station_id"],
            "msg": "String should have at least 1 character",
            "type": "string_too_short"
        }]
    )


class PaginatedWeatherObservationRead(BaseModel):
    """Paginated response for weather observations.
    
    Version-safe response contract for querying weather observations with pagination
    metadata. Supports forward compatibility through sealed field structure.
    
    Attributes:
        items: List of observation records for the current page
        total: Total count of observations matching the filter criteria
        skip: Number of records skipped (pagination offset)
        limit: Maximum records per page
    """
    items: list[WeatherObservationRead] = Field(
        description="Observations for the current page, ordered by date descending",
        examples=[[{
            "id": 1,
            "station_id": "USC00110072",
            "observation_date": "2023-06-15",
            "max_temp_c": "28.5",
            "min_temp_c": "16.2",
            "precipitation_cm": "0.0",
            "source_file": "USC00110072.txt",
            "created_at": "2024-01-15T10:30:00"
        }]]
    )
    total: int = Field(
        description="Total number of observations matching filter criteria",
        ge=0,
        example=1250
    )
    skip: int = Field(
        description="Number of records skipped (pagination offset)",
        ge=0,
        example=0
    )
    limit: int = Field(
        description="Maximum records returned per page",
        ge=1,
        le=1000,
        example=100
    )


class PaginatedWeatherYearlyStatRead(BaseModel):
    """Paginated response for yearly weather statistics.
    
    Version-safe response contract for querying aggregated yearly stats.
    Includes pagination metadata and timestamps for operational visibility.
    Supports forward compatibility through sealed field structure.
    
    Attributes:
        items: List of yearly stat records for the current page
        total: Total count of stats matching the filter criteria
        skip: Number of records skipped (pagination offset)
        limit: Maximum records per page
    """
    items: list[WeatherYearlyStatRead] = Field(
        description="Yearly statistics for the current page, ordered by year descending",
        examples=[[{
            "id": 1,
            "station_id": "USC00110072",
            "year": 2023,
            "avg_max_temp_c": "24.3",
            "avg_min_temp_c": "12.8",
            "total_precipitation_cm": "125.4",
            "observation_count": 365,
            "created_at": "2024-01-01T00:00:00"
        }]]
    )
    total: int = Field(
        description="Total number of yearly statistics matching filter criteria",
        ge=0,
        example=50
    )
    skip: int = Field(
        description="Number of records skipped (pagination offset)",
        ge=0,
        example=1
    )
    limit: int = Field(
        description="Maximum records returned per page",
        ge=1,
        le=1000,
        example=100
    )
