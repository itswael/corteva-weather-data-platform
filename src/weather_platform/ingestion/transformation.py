"""Unit conversion and measurement transformation services.

This module implements the Strategy pattern for flexible measurement unit
conversions. Supports different conversion strategies for different measurement
types (temperature, precipitation, etc.).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from weather_platform.schemas.weather import WeatherObservationCreate


class MeasurementConversionStrategy(ABC):
    """Strategy interface for converting numeric measurement values.
    
    Defines the contract for measurement conversion implementations.
    Supports any linear unit conversion (scaling + precision).
    """

    @abstractmethod
    def convert(self, value: Decimal | None) -> Decimal | None:
        """Convert a measurement value.
        
        Args:
            value: Original measurement value, or None if missing
            
        Returns:
            Decimal | None: Converted value or None if input was None
        """
        raise NotImplementedError


class ScalingMeasurementConversionStrategy(MeasurementConversionStrategy):
    """Base strategy for linear unit conversions using a scale factor.
    
    Applies formula: output = (input * scale).quantize(precision)
    Useful for unit conversions like:
    - Tenths to standard units (multiply by 0.1)
    - Millimeters to centimeters (multiply by 0.1)
    - Millimeters to inches (multiply by ~0.0394)
    
    Attributes:
        scale: Decimal scale factor for conversion
        quantize_to: Decimal precision for rounding (default: 0.01 for 2 decimal places)
    """

    def __init__(self, scale: Decimal, quantize_to: Decimal = Decimal("0.01")) -> None:
        """Initialize strategy with scale factor and precision.
        
        Args:
            scale: Multiplication factor (e.g., Decimal("0.1"))
            quantize_to: Precision for rounding (e.g., Decimal("0.01") for 2 decimal places)
        """
        self.scale = scale
        self.quantize_to = quantize_to

    def convert(self, value: Decimal | None) -> Decimal | None:
        """Convert value by multiplying by scale factor and quantizing.
        
        Args:
            value: Original value or None
            
        Returns:
            Decimal | None: Scaled and quantized value, or None if input was None
        """
        if value is None:
            return None
        return (value * self.scale).quantize(self.quantize_to)


class TenthsCelsiusToCelsiusStrategy(ScalingMeasurementConversionStrategy):
    """Convert tenths of Celsius to standard Celsius.
    
    Used for temperature data where file stores values as tenths
    (e.g., 120 in file = 12.0°C after conversion).
    
    Example:
        120 (tenths) -> 12.0 (Celsius)
        -50 (tenths) -> -5.0 (Celsius)
    """

    def __init__(self) -> None:
        """Initialize with 0.1 scale factor for tenths to standard conversion."""
        super().__init__(Decimal("0.1"))


class TenthsMillimetersToCentimetersStrategy(ScalingMeasurementConversionStrategy):
    """Convert tenths of millimeters to centimeters.
    
    Used for precipitation data where file stores values as tenths of millimeters
    (e.g., 150 in file = 1.5 cm after conversion).
    
    Example:
        150 (tenths of mm) -> 1.50 (cm)
        50 (tenths of mm) -> 0.50 (cm)
    """

    def __init__(self) -> None:
        """Initialize with 0.01 scale factor for tenths of mm to cm conversion."""
        super().__init__(Decimal("0.01"))


@dataclass(frozen=True, slots=True)
class WeatherObservationTransformationService:
    """Service for transforming raw measurements into database-ready observations.
    
    Coordinates multiple measurement conversion strategies and converts raw
    parsed values into WeatherObservationCreate DTOs with standardized units.
    
    Attributes:
        max_temp_strategy: Strategy for maximum temperature conversion
        min_temp_strategy: Strategy for minimum temperature conversion
        precipitation_strategy: Strategy for precipitation conversion
    """

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
        """Transform raw measurements into a WeatherObservationCreate schema.
        
        Applies all configured conversion strategies to transform raw file values
        into standardized units (Celsius, centimeters).
        
        Args:
            station_id: NOAA station identifier
            observation_date: Date of observation
            max_temp_raw: Raw maximum temperature (tenths of Celsius or None)
            min_temp_raw: Raw minimum temperature (tenths of Celsius or None)
            precipitation_raw: Raw precipitation (tenths of millimeters or None)
            source_file: Filename for audit tracking
            
        Returns:
            WeatherObservationCreate: Transformed observation with standardized units
        """
        return WeatherObservationCreate(
            station_id=station_id,
            observation_date=observation_date,
            max_temp_c=self.max_temp_strategy.convert(max_temp_raw),
            min_temp_c=self.min_temp_strategy.convert(min_temp_raw),
            precipitation_cm=self.precipitation_strategy.convert(precipitation_raw),
            source_file=source_file,
        )


def build_weather_observation_transformation_service() -> WeatherObservationTransformationService:
    """Factory function for default transformation service.
    
    Creates a transformation service with standard strategies:
    - Temperature: Tenths Celsius → Celsius (multiply by 0.1)
    - Precipitation: Tenths millimeters → centimeters (multiply by 0.01)
    
    Returns:
        WeatherObservationTransformationService: Configured service ready for use
    """
    return WeatherObservationTransformationService(
        max_temp_strategy=TenthsCelsiusToCelsiusStrategy(),
        min_temp_strategy=TenthsCelsiusToCelsiusStrategy(),
        precipitation_strategy=TenthsMillimetersToCentimetersStrategy(),
    )