from fastapi import Depends

from weather_platform.config.database import UnitOfWork, get_uow
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService
from weather_platform.services.aggregation import WeatherAggregationService


def get_weather_repository(uow: UnitOfWork = Depends(get_uow)) -> SQLAlchemyWeatherRepository:
    """Dependency that provides a weather repository scoped to request.
    
    Repository has access to the current request's database session via UnitOfWork.
    
    Args:
        uow: Unit of Work with active session (injected by FastAPI)
        
    Returns:
        SQLAlchemyWeatherRepository: Repository scoped to request session
    """
    assert uow.session is not None
    return SQLAlchemyWeatherRepository(uow.session)


def get_weather_service(
    repository: SQLAlchemyWeatherRepository = Depends(get_weather_repository),
) -> WeatherService:
    """Dependency that provides a configured WeatherService instance.
    
    Creates a service with access to the repository (which has access to the
    current request's database session). Service coordinates repository operations
    and implements business logic.
    
    Args:
        repository: Repository instance (injected by FastAPI via get_weather_repository)
        
    Returns:
        WeatherService: Service scoped to request session
    """
    return WeatherService(repository)


def get_aggregation_service(
    repository: SQLAlchemyWeatherRepository = Depends(get_weather_repository),
) -> WeatherAggregationService:
    """Dependency that provides a configured WeatherAggregationService instance.
    
    Creates an aggregation service for calculating yearly statistics from
    observations. Service is scoped to request's database session.
    
    Args:
        repository: Repository instance (injected by FastAPI via get_weather_repository)
        
    Returns:
        WeatherAggregationService: Aggregation service scoped to request session
    """
    return WeatherAggregationService(repository)
