"""FastAPI dependency injection for service layer access.

This module provides FastAPI dependencies that inject service and repository
instances into route handlers. Implements a clean separation between HTTP
handling (routers) and business logic (services/repositories).

Dependency injection flow:
1. Route asks for WeatherService via Depends(get_weather_service)
2. FastAPI resolves dependencies bottom-up:
   - get_weather_service depends on get_weather_repository
   - get_weather_repository depends on get_uow
   - get_uow creates a UnitOfWork with transactional session
3. Route receives fully initialized service ready to use
4. Transaction commits/rolls back automatically when request completes
"""
from fastapi import Depends

from weather_platform.config.database import UnitOfWork, get_uow
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService


def get_weather_repository(uow: UnitOfWork = Depends(get_uow)) -> SQLAlchemyWeatherRepository:
    """Dependency that provides a configured WeatherRepository instance.
    
    Creates a repository backed by the current request's transactional session.
    Repository manages all database operations for weather data.
    
    Args:
        uow: Unit of Work with active database session (injected by FastAPI)
        
    Returns:
        SQLAlchemyWeatherRepository: Repository scoped to request session
        
    Raises:
        AssertionError: If UnitOfWork session not initialized (should not occur)
    """
    # Verify session is initialized by UnitOfWork context manager
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
        
    Example (in route handler):
        @router.get("/observations/{station_id}")
        def list_observations(
            station_id: str,
            service: WeatherService = Depends(get_weather_service)
        ):
            return service.list_yearly_stats(station_id)
    """
    return WeatherService(repository)
