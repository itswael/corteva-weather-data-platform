"""CLI commands for weather data ingestion."""
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
from weather_platform.utils.logger import configure_logging
from weather_platform.utils.structured_logging import log_structured_event


def _bootstrap_ingestion_stack(env: Optional[str] = None) -> tuple[WeatherService, WeatherFileIngestor]:
    """Bootstrap the service and ingestion stack with dependency injection.

    Args:
        env: Environment name (local, test, prod). Defaults to LOCAL.

    Returns:
        Tuple of (WeatherService, WeatherFileIngestor) ready for ingestion.
    """
    settings = get_settings(env=env)
    configure_logging(settings.log_level)

    # Initialize database engine and session factory
    engine, session_local = configure_engine_and_session(settings=settings)

    # Create a session for this ingestion operation
    session = session_local()

    # Wire repository and service
    repository = SQLAlchemyWeatherRepository(session=session)
    service = WeatherService(repository=repository)

    # Wire parser and ingestor
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
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging output",
)
def ingest(file_path: Path, env: str, verbose: bool) -> None:
    """Ingest weather observations from a weather station data file.

    FILE_PATH is the path to the weather station text file to ingest.
    Each line should contain: YYYYMMDD max_temp min_temp precipitation

    Example:
        ingest-weather data/USC00110072.txt --env prod
    """
    try:
        # Log ingestion initiation with production context
        log_structured_event(
            "weather_file_ingestion_started",
            file_path=str(file_path),
            environment=env,
            verbose=verbose,
        )

        # Bootstrap the service stack
        service, ingestor = _bootstrap_ingestion_stack(env=env)

        # Perform ingestion (re-runnable via ON CONFLICT DO NOTHING)
        summary = ingestor.ingest_file(file_path)

        # Log ingestion completion with summary statistics
        log_structured_event(
            "weather_file_ingestion_summary",
            file_path=file_path.name,
            environment=env,
            processed=summary.processed,
            inserted=summary.inserted,
            skipped_duplicates=summary.skipped_duplicates,
            duration_ms=summary.duration_ms,
            status="success",
        )

        # Print human-readable summary
        click.echo(f"\n✓ Ingestion completed successfully")
        click.echo(f"  File: {file_path.name}")
        click.echo(f"  Processed: {summary.processed}")
        click.echo(f"  Inserted: {summary.inserted}")
        click.echo(f"  Skipped (duplicates): {summary.skipped_duplicates}")
        click.echo(f"  Duration: {summary.duration_ms}ms")

        sys.exit(0)

    except WeatherFileParseError as exc:
        # Log parse errors with context
        log_structured_event(
            "weather_file_ingestion_failed",
            file_path=file_path.name,
            environment=env,
            error_type="parse_error",
            error_message=str(exc),
            status="failed",
        )
        click.echo(f"\n✗ Parse error: {exc}", err=True)
        sys.exit(1)

    except FileNotFoundError as exc:
        # Log file not found
        log_structured_event(
            "weather_file_ingestion_failed",
            file_path=str(file_path),
            environment=env,
            error_type="file_not_found",
            error_message=str(exc),
            status="failed",
        )
        click.echo(f"\n✗ File not found: {file_path}", err=True)
        sys.exit(1)

    except Exception as exc:
        # Log unexpected errors
        log_structured_event(
            "weather_file_ingestion_failed",
            file_path=file_path.name if isinstance(file_path, Path) else str(file_path),
            environment=env,
            error_type=type(exc).__name__,
            error_message=str(exc),
            status="failed",
        )
        click.echo(f"\n✗ Unexpected error: {exc}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    ingest()
