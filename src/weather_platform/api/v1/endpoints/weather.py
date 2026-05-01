"""Weather data API endpoints for observations and yearly statistics.

Provides REST endpoints for querying and creating weather observations
and yearly aggregated statistics. All endpoints are backed by the service
layer which coordinates repository operations and business logic.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from weather_platform.api.dependencies import get_weather_service
from weather_platform.schemas.weather import (
    WeatherObservationCreate,
    WeatherObservationRead,
    WeatherYearlyStatCreate,
    WeatherYearlyStatRead,
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
    """Create a new weather observation.
    
    Inserts a daily weather observation for a specific station and date.
    Uses database-level UNIQUE constraint to skip duplicates on re-ingestion.
    
    Request Body (WeatherObservationCreate):
        - station_id: NOAA station identifier (required)
        - observation_date: Date of observation (required)
        - max_temp_c: Maximum temperature in Celsius (optional)
        - min_temp_c: Minimum temperature in Celsius (optional)
        - precipitation_cm: Precipitation in centimeters (optional)
        - source_file: Data file this came from (optional, audit field)
    
    Returns:
        WeatherObservationRead: Created observation with id and created_at
        
    Response (201 Created):
        {
            "id": 1,
            "station_id": "USC00110072",
            "observation_date": "2023-01-01",
            "max_temp_c": "15.5",
            "min_temp_c": "8.3",
            "precipitation_cm": "0.25",
            "source_file": "USC00110072.txt",
            "created_at": "2024-01-15T10:30:00"
        }
    """
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
    """Retrieve a specific weather observation.
    
    Fetches a single daily observation for a station on a specific date.
    
    Path Parameters:
        station_id: NOAA station identifier (e.g., USC00110072)
        observation_date: Date in YYYY-MM-DD format
    
    Returns:
        WeatherObservationRead: Observation data if found
        
    Raises:
        HTTPException: 404 Not Found if no observation exists for station/date
        
    Example:
        GET /weather/observations/USC00110072/2023-01-01
    """
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
    """Create or update yearly weather statistics for a station.
    
    Stores aggregated annual statistics (averages and totals) for a station.
    Updates existing record if one exists for the station/year combination.
    
    Request Body (WeatherYearlyStatCreate):
        - station_id: NOAA station identifier (required)
        - year: Calendar year (required, 1800-3000)
        - avg_max_temp_c: Average daily maximum temperature (optional)
        - avg_min_temp_c: Average daily minimum temperature (optional)
        - total_precipitation_cm: Sum of daily precipitation (optional)
        - observation_count: Number of daily observations (required, >= 0)
    
    Returns:
        WeatherYearlyStatRead: Created/updated statistics with id and created_at
        
    Response (201 Created or Updated):
        {
            "id": 42,
            "station_id": "USC00110072",
            "year": 2023,
            "avg_max_temp_c": "18.5",
            "avg_min_temp_c": "9.2",
            "total_precipitation_cm": "85.3",
            "observation_count": 365,
            "created_at": "2024-01-15T10:30:00"
        }
    """
    return service.upsert_yearly_stat(payload)


@router.get("/yearly-stats/{station_id}", response_model=list[WeatherYearlyStatRead])
def list_yearly_stats(
    station_id: str,
    service: WeatherService = Depends(get_weather_service),
) -> list[WeatherYearlyStatRead]:
    """List all yearly statistics for a weather station.
    
    Retrieves yearly aggregated statistics (e.g., annual averages) for all years
    available for a specific station.
    
    Path Parameters:
        station_id: NOAA station identifier (e.g., USC00110072)
    
    Returns:
        list[WeatherYearlyStatRead]: List of yearly statistics, ordered by year
        
    Example:
        GET /weather/yearly-stats/USC00110072
        
        Returns:
        [
            {
                "id": 1,
                "station_id": "USC00110072",
                "year": 2020,
                "avg_max_temp_c": "17.2",
                ...
            },
            {
                "id": 2,
                "station_id": "USC00110072",
                "year": 2021,
                "avg_max_temp_c": "18.5",
                ...
            }
        ]
    """
    return list(service.list_yearly_stats(station_id))
