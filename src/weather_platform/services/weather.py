from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from collections.abc import Sequence
from collections.abc import Iterable
from time import perf_counter

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    processed: int
    inserted: int
    skipped_duplicates: int
    duration_ms: int


class WeatherService:
    def __init__(self, repository: WeatherRepository) -> None:
        self.repository = repository

    def ingest_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        return self.repository.upsert_observation(observation)

    def ingest_observations(self, observations: Iterable[WeatherObservationCreate]) -> IngestionSummary:
        started_at = perf_counter()
        processed = 0
        inserted = 0

        for observation in observations:
            processed += 1
            if self.repository.insert_observation_if_missing(observation):
                inserted += 1

        skipped_duplicates = processed - inserted
        duration_ms = int((perf_counter() - started_at) * 1000)
        summary = IngestionSummary(
            processed=processed,
            inserted=inserted,
            skipped_duplicates=skipped_duplicates,
            duration_ms=duration_ms,
        )
        return summary

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        return self.repository.get_observation(station_id, observation_date)

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        return self.repository.upsert_yearly_stat(stat)

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        return self.repository.list_yearly_stats(station_id)
