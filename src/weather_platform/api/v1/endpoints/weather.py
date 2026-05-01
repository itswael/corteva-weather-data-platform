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
