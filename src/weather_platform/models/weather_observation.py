from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from weather_platform.models.base import Base, TimestampMixin


class WeatherObservation(TimestampMixin, Base):
    __tablename__ = "weather_observations"
    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "observation_date",
            name="uq_weather_observations_station_date",
        ),
        Index("ix_weather_observations_station_date", "station_id", "observation_date"),
        Index("ix_weather_observations_observation_date", "observation_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(String, nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    max_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    precipitation_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return (
            "WeatherObservation("
            f"station_id={self.station_id!r}, observation_date={self.observation_date!r})"
        )
