"""SQLAlchemy models for the Weather Platform."""

from weather_platform.models.base import Base, BaseEntity
from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat

__all__ = ["Base", "BaseEntity", "WeatherObservation", "WeatherYearlyStat"]
