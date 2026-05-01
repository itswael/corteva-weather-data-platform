from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WeatherObservationCreate(BaseModel):
    station_id: str = Field(min_length=1)
    observation_date: date
    max_temp_c: Decimal | None = None
    min_temp_c: Decimal | None = None
    precipitation_cm: Decimal | None = None
    source_file: str | None = None


class WeatherObservationRead(WeatherObservationCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeatherYearlyStatCreate(BaseModel):
    station_id: str = Field(min_length=1)
    year: int = Field(ge=1800, le=3000)
    avg_max_temp_c: Decimal | None = None
    avg_min_temp_c: Decimal | None = None
    total_precipitation_cm: Decimal | None = None
    observation_count: int = Field(ge=0)


class WeatherYearlyStatRead(WeatherYearlyStatCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
