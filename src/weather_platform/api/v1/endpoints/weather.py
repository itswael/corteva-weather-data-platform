"""Weather API endpoints with production-ready OpenAPI documentation.

Provides comprehensive HTTP interfaces for weather observation and statistics:
- POST /observations: Ingest or update weather observations (upsert)
- GET /observations/{station_id}/{observation_date}: Retrieve specific observation
- POST /yearly-stats: Ingest or update yearly statistics (upsert)
- GET /yearly-stats/{station_id}: List all yearly stats for a station
- GET /observations: Query observations with pagination and filtering
- GET /stats: Query yearly statistics with pagination and filtering

All endpoints follow OpenAPI 3.1.0 specification with comprehensive documentation,
examples, validation rules, and error responses for production deployments.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from weather_platform.api.dependencies import get_weather_service
from weather_platform.schemas.weather import (
    WeatherObservationCreate,
    WeatherObservationRead,
    WeatherYearlyStatCreate,
    WeatherYearlyStatRead,
    PaginatedWeatherObservationRead,
    PaginatedWeatherYearlyStatRead,
    HTTPErrorResponse,
    ValidationErrorResponse,
)
from weather_platform.services.weather import WeatherService

router = APIRouter(
    prefix="/weather",
    tags=["weather"],
    responses={
        422: {
            "model": ValidationErrorResponse,
            "description": "Request validation failed (invalid query parameters, request body, or path parameter format)",
        },
        500: {
            "model": HTTPErrorResponse,
            "description": "Internal server error (database connectivity issues, unexpected failures)",
        },
    },
)


@router.post(
    "/observations",
    response_model=WeatherObservationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Observation created or updated successfully (idempotent upsert)",
            "model": WeatherObservationRead,
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "station_id": "USC00110072",
                        "observation_date": "2023-06-15",
                        "max_temp_c": "28.5",
                        "min_temp_c": "16.2",
                        "precipitation_cm": "0.0",
                        "source_file": "USC00110072.txt",
                        "created_at": "2024-01-15T10:30:00",
                    }
                }
            },
        },
    },
)
def ingest_observation(
    payload: WeatherObservationCreate,
    service: WeatherService = Depends(get_weather_service),
) -> WeatherObservationRead:
    """Create or update a weather observation (upsert).
    
    Ingests a single daily weather observation for a station. If an observation with the
    same station_id and observation_date already exists, it is updated (idempotent).
    This operation is safe for reprocessing historical data.
    
    Temperatures and precipitation values are optional to support sparse data from
    historical weather files where some measurements may be unavailable.
    
    Status Codes:
        201: Observation successfully created or updated
        422: Request validation failed (missing required field, invalid data type)
        500: Database error or unexpected server failure
    """
    return service.ingest_observation(payload)


@router.get(
    "/observations/{station_id}/{observation_date}",
    response_model=WeatherObservationRead,
    responses={
        200: {
            "description": "Observation retrieved successfully",
            "model": WeatherObservationRead,
        },
        404: {
            "description": "Observation not found for the specified station and date",
            "model": HTTPErrorResponse,
        },
    },
)
def get_observation(
    station_id: str = Path(..., description="NOAA station identifier (e.g., USC00110072)"),
    observation_date: date = Path(..., description="Observation date (YYYY-MM-DD format)"),
    service: WeatherService = Depends(get_weather_service),
) -> WeatherObservationRead:
    """Retrieve a specific weather observation by station and date.
    
    Fetches a single observation record for the given station_id and observation_date.
    Returns 404 if no matching observation exists.
    
    Status Codes:
        200: Observation retrieved successfully
        404: No observation found for the specified station and date
        422: Path parameter validation failed (invalid date format)
        500: Database error or unexpected server failure
    """
    observation = service.get_observation(station_id, observation_date)
    if observation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found")
    return observation


@router.post(
    "/yearly-stats",
    response_model=WeatherYearlyStatRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Yearly statistic created or updated successfully (idempotent upsert)",
            "model": WeatherYearlyStatRead,
        },
    },
)
def upsert_yearly_stat(
    payload: WeatherYearlyStatCreate,
    service: WeatherService = Depends(get_weather_service),
) -> WeatherYearlyStatRead:
    """Create or update yearly weather statistics (upsert).
    
    Ingests aggregated annual statistics for a station. If statistics already exist
    for the same station_id and year, they are updated (idempotent). This operation
    is safe for reprocessing yearly aggregations.
    
    Status Codes:
        201: Yearly stat successfully created or updated
        422: Request validation failed (invalid year range, negative observation_count)
        500: Database error or unexpected server failure
    """
    return service.upsert_yearly_stat(payload)


@router.get(
    "/yearly-stats/{station_id}",
    response_model=list[WeatherYearlyStatRead],
    responses={
        200: {
            "description": "Yearly statistics retrieved successfully (may be empty list if no data)",
            "model": list[WeatherYearlyStatRead],
        },
    },
)
def list_yearly_stats(
    station_id: str = Path(..., min_length=1, description="NOAA station identifier (e.g., USC00110072)"),
    service: WeatherService = Depends(get_weather_service),
) -> list[WeatherYearlyStatRead]:
    """List all yearly statistics for a station.
    
    Retrieves all available yearly aggregated statistics for the specified station,
    ordered by year ascending (oldest years first). Returns an empty list if
    the station has no yearly statistics.
    
    Status Codes:
        200: Yearly statistics retrieved successfully
        422: Station identifier validation failed (empty string)
        500: Database error or unexpected server failure
    """
    return list(service.list_yearly_stats(station_id))


@router.get(
    "/observations",
    response_model=PaginatedWeatherObservationRead,
    responses={
        200: {
            "description": "Observations retrieved successfully",
            "model": PaginatedWeatherObservationRead,
        },
    },
)
def query_observations(
    skip: int = Query(0, ge=0, description="Pagination offset - number of records to skip", example=0),
    limit: int = Query(100, ge=1, le=1000, description="Page size (max 1000, capped server-side)", example=100),
    station_id: str | None = Query(None, description="Optional filter by station identifier", example="USC00110072"),
    start_date: date | None = Query(None, description="Optional minimum date (YYYY-MM-DD, inclusive)", example="2023-01-01"),
    end_date: date | None = Query(None, description="Optional maximum date (YYYY-MM-DD, inclusive)", example="2023-12-31"),
    service: WeatherService = Depends(get_weather_service),
) -> PaginatedWeatherObservationRead:
    """Query weather observations with pagination and filtering.
    
    Returns a paginated list of weather observations optionally filtered by station
    and date range. Results are ordered by observation_date descending (most recent first).
    
    Query Parameters:
        skip: Pagination offset in records (default: 0)
        limit: Page size, max 1000 (default: 100, capped server-side for performance)
        station_id: Optional filter by NOAA station identifier (exact match)
        start_date: Optional minimum observation date (inclusive)
        end_date: Optional maximum observation date (inclusive)
    
    Returns:
        PaginatedWeatherObservationRead: Page of observations with total count and pagination metadata
    
    Status Codes:
        200: Observations retrieved successfully
        422: Query parameter validation failed (invalid date format, limit > 1000)
        500: Database error or unexpected server failure
    """
    return service.query_observations(
        skip=skip,
        limit=limit,
        station_id=station_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/stats",
    response_model=PaginatedWeatherYearlyStatRead,
    responses={
        200: {
            "description": "Yearly statistics retrieved successfully",
            "model": PaginatedWeatherYearlyStatRead,
        },
    },
)
def query_yearly_stats(
    skip: int = Query(0, ge=0, description="Pagination offset - number of records to skip", example=0),
    limit: int = Query(100, ge=1, le=1000, description="Page size (max 1000, capped server-side)", example=100),
    station_id: str | None = Query(None, description="Optional filter by station identifier", example="USC00110072"),
    start_year: int | None = Query(None, ge=1800, le=3000, description="Optional minimum year (inclusive)", example=2020),
    end_year: int | None = Query(None, ge=1800, le=3000, description="Optional maximum year (inclusive)", example=2023),
    service: WeatherService = Depends(get_weather_service),
) -> PaginatedWeatherYearlyStatRead:
    """Query yearly weather statistics with pagination and filtering.
    
    Returns a paginated list of yearly aggregated weather statistics optionally filtered
    by station and year range. Results are ordered by year descending (most recent years first).
    
    Query Parameters:
        skip: Pagination offset in records (default: 0)
        limit: Page size, max 1000 (default: 100, capped server-side for performance)
        station_id: Optional filter by NOAA station identifier (exact match)
        start_year: Optional minimum year (inclusive, valid 1800-3000)
        end_year: Optional maximum year (inclusive, valid 1800-3000)
    
    Returns:
        PaginatedWeatherYearlyStatRead: Page of yearly stats with total count and pagination metadata
    
    Status Codes:
        200: Yearly statistics retrieved successfully
        422: Query parameter validation failed (invalid year range, limit > 1000)
        500: Database error or unexpected server failure
    """
    return service.query_yearly_stats(
        skip=skip,
        limit=limit,
        station_id=station_id,
        start_year=start_year,
        end_year=end_year,
    )
