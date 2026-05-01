# Weather Platform Foundation

Production-grade FastAPI scaffold using clean architecture, dependency injection, a repository layer, PostgreSQL, and Alembic.

## Structure

- `src/weather_platform/api` - API routers and dependencies
- `src/weather_platform/cli` - CLI commands for data ingestion
- `src/weather_platform/services` - application services
- `src/weather_platform/repositories` - persistence abstractions and SQLAlchemy implementations
- `src/weather_platform/models` - SQLAlchemy ORM models
- `src/weather_platform/schemas` - Pydantic DTOs
- `src/weather_platform/ingestion` - ingestion orchestration
- `src/weather_platform/config` - settings and database wiring
- `src/weather_platform/utils` - shared utilities
- `migrations` - Alembic environment and revisions
- `tests` - unit and integration tests

## Local workflow

```bash
cp .env.example .env
make install
make test
make run
```

## CLI: Weather Data Ingestion

Ingest weather observations from station data files:

```bash
# Basic ingestion (local development)
ingest-weather data/USC00110072.txt

# Production ingestion
ingest-weather data/USC00110072.txt --env prod

# Verbose mode with detailed error logging
ingest-weather data/USC00110072.txt --env prod --verbose
```

See [CLI documentation](docs/CLI.md) for detailed usage and examples.
