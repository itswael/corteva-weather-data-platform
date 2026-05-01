from collections.abc import Iterable

from weather_platform.schemas.weather import WeatherObservationCreate
from weather_platform.services.weather import WeatherService


class WeatherFileIngestor:
    def __init__(self, service: WeatherService) -> None:
        self.service = service

    def ingest(self, records: Iterable[WeatherObservationCreate]):
        return [self.service.ingest_observation(record) for record in records]
