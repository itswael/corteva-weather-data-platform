from datetime import date
from collections.abc import Sequence

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class WeatherService:
    def __init__(self, repository: WeatherRepository) -> None:
        self.repository = repository

    def ingest_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        return self.repository.upsert_observation(observation)

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        return self.repository.get_observation(station_id, observation_date)

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        return self.repository.upsert_yearly_stat(stat)

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        return self.repository.list_yearly_stats(station_id)
