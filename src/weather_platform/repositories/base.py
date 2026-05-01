from collections.abc import Sequence
from datetime import date
from typing import Protocol

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class WeatherRepository(Protocol):
    def upsert_observation(self, observation: WeatherObservationCreate) -> WeatherObservation: ...

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None: ...

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat: ...

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]: ...
