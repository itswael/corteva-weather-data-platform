"""CLI commands for weather data ingestion and aggregation."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from weather_platform.config.database import configure_engine_and_session
from weather_platform.config.settings import get_settings
from weather_platform.ingestion.ingest_weather_file import (
    WeatherFileIngestor,
    WeatherStationTextFileParser,
    WeatherFileParseError,
)
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository
from weather_platform.services.weather import WeatherService
from weather_platform.services.aggregation import WeatherAggregationService
from weather_platform.utils.logger import configure_logging
from weather_platform.utils.structured_logging import log_structured_event


def _bootstrap_ingestion_stack(env: Optional[str] = None) -> tuple[WeatherService, WeatherFileIngestor]:
    """Bootstrap the service and ingestion stack with dependency injection.
    
    Performs complete setup of the data ingestion pipeline:
    1. Load environment-specific settings
    2. Configure logging
    3. Create database engine and session factory
    4. Create repository layer (SQLAlchemy-based)
    5. Create service layer (orchestrates repository operations)
    6. Create parser (converts raw file text to data objects)
    7. Create ingestor (orchestrates parse → validate → transform → store)

    Args:
        env: Environment name (local, test, prod). Defaults to APP_ENV or "local".

    Returns:
        tuple[WeatherService, WeatherFileIngestor]: Service and ingestor ready for use.
    """
    # Load environment-appropriate settings
    settings = get_settings(env=env)
    
    # Configure application logging based on settings
    configure_logging(settings.log_level)

    # Initialize database engine and session factory
    engine, session_local = configure_engine_and_session(settings=settings)

    # Create a session for this ingestion operation
    session = session_local()

    # Wire repository and service layers
    repository = SQLAlchemyWeatherRepository(session=session)
    service = WeatherService(repository=repository)

    # Wire parser and ingestor layers
    parser = WeatherStationTextFileParser()
    ingestor = WeatherFileIngestor(service=service, parser=parser)

    return service, ingestor


@click.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--env",
    type=click.Choice(["local", "test", "prod"], case_sensitive=False),
    default="local",
    help="Environment configuration (default: local)",
)
def ingest(file_path: Path, env: str) -> None:
    """Ingest weather observations from a weather station data file.
    
    FILE_PATH: Path to NOAA weather station text file
    Format: YYYYMMDD max_temp min_temp precipitation (one per line)
    Units: Temperature in tenths of Celsius, Precipitation in tenths of mm
    """
    try:
        log_structured_event(
            "weather_file_ingestion_started",
            file_path=str(file_path),
            environment=env,
        )

        service, ingestor = _bootstrap_ingestion_stack(env=env)
        summary = ingestor.ingest_file(file_path)

        log_structured_event(
            "weather_file_ingestion_completed",
            file_path=file_path.name,
            processed=summary.processed,
            inserted=summary.inserted,
            skipped_duplicates=summary.skipped_duplicates,
            status="success",
        )

        click.echo(f"\n✓ Ingestion completed")
        click.echo(f"  Processed: {summary.processed}, Inserted: {summary.inserted}, Skipped: {summary.skipped_duplicates}")

        sys.exit(0)

    except WeatherFileParseError as exc:
        log_structured_event(
            "weather_file_ingestion_failed",
            file_path=file_path.name,
            error=str(exc),
            status="failed",
        )
        click.echo(f"\n✗ Ingestion failed: {exc}", err=True)
        sys.exit(1)


@click.command()
@click.argument("station_id", type=str)
@click.argument("year", type=int)
@click.option(
    "--env",
    type=click.Choice(["local", "test", "prod"], case_sensitive=False),
    default="local",
    help="Environment configuration (default: local)",
)
def aggregate_year(station_id: str, year: int, env: str) -> None:
    """Calculate yearly aggregated weather statistics for a station.
    
    STATION_ID: NOAA station identifier (e.g., USC00110072)
    YEAR: Calendar year to aggregate (e.g., 2023)
    
    Aggregates daily observations, calculating:
    - Average max/min temperature (ignoring NULLs)
    - Total precipitation (ignoring NULLs)
    - Observation count
    """
    try:
        log_structured_event(
            "weather_aggregation_started",
            station_id=station_id,
            year=year,
            environment=env,
        )
        
        # Setup
        settings = get_settings(env=env)
        configure_logging(settings.log_level)
        engine, session_local = configure_engine_and_session(settings=settings)
        session = session_local()
        
        # Create service
        repository = SQLAlchemyWeatherRepository(session=session)
        aggregation_service = WeatherAggregationService(repository)
        
        # Aggregate
        yearly_stat, summary = aggregation_service.aggregate_year(station_id, year)
        
        log_structured_event(
            "weather_aggregation_completed",
            station_id=station_id,
            year=year,
            observations=summary.observations_processed,
            status="success",
        )
        
        click.echo(f"\n✓ Aggregation completed for {station_id} ({year})")
        click.echo(f"  Observations: {summary.observations_processed}")
        click.echo(f"  Avg max temp: {yearly_stat.avg_max_temp_c}°C")
        click.echo(f"  Avg min temp: {yearly_stat.avg_min_temp_c}°C")
        click.echo(f"  Total precipitation: {yearly_stat.total_precipitation_cm} cm")
        
        session.close()
        sys.exit(0)
        
    except Exception as exc:
        log_structured_event(
            "weather_aggregation_failed",
            station_id=station_id,
            year=year,
            error=str(exc),
            status="failed",
        )
        click.echo(f"\n✗ Aggregation failed: {exc}", err=True)
        sys.exit(1)
