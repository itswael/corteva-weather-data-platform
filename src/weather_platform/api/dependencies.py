from fastapi import Depends

from weather_platform.config.database import UnitOfWork, get_uow
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService


def get_weather_repository(uow: UnitOfWork = Depends(get_uow)) -> SQLAlchemyWeatherRepository:
    assert uow.session is not None
    return SQLAlchemyWeatherRepository(uow.session)


def get_weather_service(
    repository: SQLAlchemyWeatherRepository = Depends(get_weather_repository),
) -> WeatherService:
    return WeatherService(repository)
