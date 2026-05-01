from datetime import date
from decimal import Decimal

from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate
from weather_platform.services.weather import WeatherService


class FakeWeatherRepository:
    def __init__(self) -> None:
        self.observations: dict[tuple[str, date], WeatherObservationCreate] = {}
        self.yearly_stats: dict[tuple[str, int], WeatherYearlyStatCreate] = {}

    def upsert_observation(self, observation: WeatherObservationCreate):
        self.observations[(observation.station_id, observation.observation_date)] = observation
        return observation

    def get_observation(self, station_id: str, observation_date: date):
        return self.observations.get((station_id, observation_date))

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate):
        self.yearly_stats[(stat.station_id, stat.year)] = stat
        return stat

    def list_yearly_stats(self, station_id: str):
        return [
            stat
            for (current_station_id, _), stat in self.yearly_stats.items()
            if current_station_id == station_id
        ]


def test_weather_service_ingests_and_reads_observations() -> None:
    repository = FakeWeatherRepository()
    service = WeatherService(repository)
    payload = WeatherObservationCreate(
        station_id="USC00110072",
        observation_date=date(2024, 4, 30),
        max_temp_c=Decimal("25.50"),
        min_temp_c=Decimal("12.00"),
        precipitation_cm=Decimal("0.20"),
        source_file="sample.txt",
    )

    saved = service.ingest_observation(payload)

    assert saved == payload
    assert service.get_observation("USC00110072", date(2024, 4, 30)) == payload
