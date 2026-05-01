from fastapi import Depends
from sqlalchemy.orm import Session

from weather_platform.config.database import get_db_session
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService


def get_weather_repository(session: Session = Depends(get_db_session)) -> SQLAlchemyWeatherRepository:
    return SQLAlchemyWeatherRepository(session)


def get_weather_service(
    repository: SQLAlchemyWeatherRepository = Depends(get_weather_repository),
) -> WeatherService:
    return WeatherService(repository)
