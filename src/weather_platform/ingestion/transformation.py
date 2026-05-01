from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from weather_platform.schemas.weather import WeatherObservationCreate


class MeasurementConversionStrategy(ABC):
    """Strategy interface for converting a numeric measurement value."""

    @abstractmethod
    def convert(self, value: Decimal | None) -> Decimal | None:
        raise NotImplementedError


class ScalingMeasurementConversionStrategy(MeasurementConversionStrategy):
    """Base strategy for linear unit conversions using a scale factor."""

    def __init__(self, scale: Decimal, quantize_to: Decimal = Decimal("0.01")) -> None:
        self.scale = scale
        self.quantize_to = quantize_to

    def convert(self, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return (value * self.scale).quantize(self.quantize_to)


class TenthsCelsiusToCelsiusStrategy(ScalingMeasurementConversionStrategy):
    """Convert tenths of Celsius to Celsius."""

    def __init__(self) -> None:
        super().__init__(Decimal("0.1"))


class TenthsMillimetersToCentimetersStrategy(ScalingMeasurementConversionStrategy):
    """Convert tenths of millimeters to centimeters."""

    def __init__(self) -> None:
        super().__init__(Decimal("0.01"))


@dataclass(frozen=True, slots=True)
class WeatherObservationTransformationService:
    """Transforms raw station values into API/database-ready DTOs."""

    max_temp_strategy: MeasurementConversionStrategy
    min_temp_strategy: MeasurementConversionStrategy
    precipitation_strategy: MeasurementConversionStrategy

    def transform(
        self,
        *,
        station_id: str,
        observation_date: date,
        max_temp_raw: Decimal | None,
        min_temp_raw: Decimal | None,
        precipitation_raw: Decimal | None,
        source_file: str,
    ) -> WeatherObservationCreate:
        return WeatherObservationCreate(
            station_id=station_id,
            observation_date=observation_date,
            max_temp_c=self.max_temp_strategy.convert(max_temp_raw),
            min_temp_c=self.min_temp_strategy.convert(min_temp_raw),
            precipitation_cm=self.precipitation_strategy.convert(precipitation_raw),
            source_file=source_file,
        )


def build_weather_observation_transformation_service() -> WeatherObservationTransformationService:
    """Factory for the default weather observation transformation strategies."""

    return WeatherObservationTransformationService(
        max_temp_strategy=TenthsCelsiusToCelsiusStrategy(),
        min_temp_strategy=TenthsCelsiusToCelsiusStrategy(),
        precipitation_strategy=TenthsMillimetersToCentimetersStrategy(),
    )