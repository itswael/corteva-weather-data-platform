from datetime import date
from decimal import Decimal

from weather_platform.ingestion import (
    TenthsCelsiusToCelsiusStrategy,
    TenthsMillimetersToCentimetersStrategy,
    WeatherObservationTransformationService,
)


class DoubleValueStrategy:
    def convert(self, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value * Decimal("2")


def test_default_conversion_strategies_scale_values() -> None:
    assert TenthsCelsiusToCelsiusStrategy().convert(Decimal("-22")) == Decimal("-2.20")
    assert TenthsMillimetersToCentimetersStrategy().convert(Decimal("94")) == Decimal("0.94")


def test_transformation_service_accepts_custom_strategies() -> None:
    service = WeatherObservationTransformationService(
        max_temp_strategy=DoubleValueStrategy(),
        min_temp_strategy=DoubleValueStrategy(),
        precipitation_strategy=DoubleValueStrategy(),
    )

    record = service.transform(
        station_id="USC00110072",
        observation_date=date(1985, 1, 1),
        max_temp_raw=Decimal("10"),
        min_temp_raw=Decimal("-5"),
        precipitation_raw=Decimal("3"),
        source_file="USC00110072.txt",
    )

    assert record.max_temp_c == Decimal("20")
    assert record.min_temp_c == Decimal("-10")
    assert record.precipitation_cm == Decimal("6")
