from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from weather_platform.api.dependencies import get_weather_service
from weather_platform.schemas.weather import (
    WeatherObservationCreate,
    WeatherObservationRead,
    WeatherYearlyStatCreate,
    WeatherYearlyStatRead,
    PaginatedWeatherObservationRead,
    PaginatedWeatherYearlyStatRead,
)
from weather_platform.services.weather import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])


@router.post(
    "/observations",
    response_model=WeatherObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_observation(
    payload: WeatherObservationCreate,
    service: WeatherService = Depends(get_weather_service),
) -> WeatherObservationRead:
    return service.ingest_observation(payload)


@router.get(
    "/observations/{station_id}/{observation_date}",
    response_model=WeatherObservationRead,
)
def get_observation(
    station_id: str,
    observation_date: date,
    service: WeatherService = Depends(get_weather_service),
) -> WeatherObservationRead:
    observation = service.get_observation(station_id, observation_date)
    if observation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found")
    return observation


@router.post(
    "/yearly-stats",
    response_model=WeatherYearlyStatRead,
    status_code=status.HTTP_201_CREATED,
)
def upsert_yearly_stat(
    payload: WeatherYearlyStatCreate,
    service: WeatherService = Depends(get_weather_service),
) -> WeatherYearlyStatRead:
    return service.upsert_yearly_stat(payload)


@router.get("/yearly-stats/{station_id}", response_model=list[WeatherYearlyStatRead])
def list_yearly_stats(
    station_id: str,
    service: WeatherService = Depends(get_weather_service),
) -> list[WeatherYearlyStatRead]:
    return list(service.list_yearly_stats(station_id))


@router.get("/observations", response_model=PaginatedWeatherObservationRead)
def query_observations(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records per page"),
    station_id: str | None = Query(None, description="Filter by station identifier"),
    start_date: date | None = Query(None, description="Minimum observation date (inclusive)"),
    end_date: date | None = Query(None, description="Maximum observation date (inclusive)"),
    service: WeatherService = Depends(get_weather_service),
) -> PaginatedWeatherObservationRead:
    """Query weather observations with pagination and filtering.
    
    Returns a paginated list of observations optionally filtered by station_id
    and date range. Results are ordered by observation date descending.
    
    Query Parameters:
        skip: Pagination offset (default: 0)
        limit: Page size, max 1000 (default: 100)
        station_id: Optional filter by NOAA station identifier
        start_date: Optional minimum date (inclusive)
        end_date: Optional maximum date (inclusive)
    
    Returns:
        PaginatedWeatherObservationRead: Observations with pagination metadata
    """
    return service.query_observations(
        skip=skip,
        limit=limit,
        station_id=station_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/stats", response_model=PaginatedWeatherYearlyStatRead)
def query_yearly_stats(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records per page"),
    station_id: str | None = Query(None, description="Filter by station identifier"),
    start_year: int | None = Query(None, ge=1800, le=3000, description="Minimum year (inclusive)"),
    end_year: int | None = Query(None, ge=1800, le=3000, description="Maximum year (inclusive)"),
    service: WeatherService = Depends(get_weather_service),
) -> PaginatedWeatherYearlyStatRead:
    """Query yearly weather statistics with pagination and filtering.
    
    Returns a paginated list of yearly aggregated statistics optionally filtered
    by station_id and year range. Results are ordered by year descending (most recent first).
    
    Query Parameters:
        skip: Pagination offset (default: 0)
        limit: Page size, max 1000 (default: 100)
        station_id: Optional filter by NOAA station identifier
        start_year: Optional minimum year (inclusive, 1800-3000)
        end_year: Optional maximum year (inclusive, 1800-3000)
    
    Returns:
        PaginatedWeatherYearlyStatRead: Yearly stats with pagination metadata
    """
    return service.query_yearly_stats(
        skip=skip,
        limit=limit,
        station_id=station_id,
        start_year=start_year,
        end_year=end_year,
    )
