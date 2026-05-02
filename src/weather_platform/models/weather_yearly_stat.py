from decimal import Decimal

from sqlalchemy import Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from weather_platform.models.base import BaseEntity


class WeatherYearlyStat(BaseEntity):
    __tablename__ = "weather_yearly_stats"
    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "year",
            name="uq_weather_yearly_stats_station_year",
        ),
        Index("ix_weather_yearly_stats_station_year", "station_id", "year"),
        Index("ix_weather_yearly_stats_station", "station_id"),
        Index("ix_weather_yearly_stats_year", "year"),
    )

    station_id: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_max_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    avg_min_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    total_precipitation_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"WeatherYearlyStat(station_id={self.station_id!r}, year={self.year!r})"
