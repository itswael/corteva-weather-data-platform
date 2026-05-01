"""Yearly weather data aggregation service.

Service layer for calculating and managing yearly weather statistics
from daily observations. Handles aggregation logic and persistence.
"""
from dataclasses import dataclass
from datetime import datetime

from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository, YearlyAggregateData
from weather_platform.schemas.weather import WeatherYearlyStatCreate


@dataclass(frozen=True)
class AggregationSummary:
    """Summary of a yearly aggregation operation.
    
    Attributes:
        station_id: Station for which stats were aggregated
        year: Year of aggregation
        observations_processed: Number of observations used in aggregation
        aggregation_completed_at: Timestamp when aggregation completed
        measurements_available: Dict of which measurements were available
            (e.g., {"max_temp": True, "min_temp": False, "precipitation": True})
    """
    station_id: str
    year: int
    observations_processed: int
    aggregation_completed_at: datetime
    measurements_available: dict[str, bool]


class WeatherAggregationService:
    """Service for calculating yearly weather statistics from observations.
    
    Implements Service Layer Pattern for weather data aggregation:
    - Queries raw observations via repository
    - Calculates aggregates (avg max/min temp, total precipitation)
    - Ignores NULL values in calculations
    - Persists results via repository
    
    Attributes:
        repository: Weather data repository for queries and persistence
    """
    
    def __init__(self, repository: WeatherRepository) -> None:
        """Initialize aggregation service with repository.
        
        Args:
            repository: WeatherRepository for data access
        """
        self.repository = repository
    
    def aggregate_year(self, station_id: str, year: int) -> tuple[WeatherYearlyStat, AggregationSummary]:
        """Calculate yearly statistics for a station and store results.
        
        Aggregates observations for the specified station/year:
        1. Queries observations from repository
        2. Calculates averages (ignoring NULLs) and totals
        3. Persists results back to repository
        4. Returns both the stored stat and summary info
        
        Args:
            station_id: NOAA station identifier
            year: Calendar year to aggregate
            
        Returns:
            tuple[WeatherYearlyStat, AggregationSummary]: 
                - Stored yearly stat record
                - Summary of aggregation operation
                
        Example:
            stat, summary = service.aggregate_year("USC00110072", 2023)
            print(f"Aggregated {summary.observations_processed} observations")
            print(f"Avg max temp: {stat.avg_max_temp_c}°C")
        """
        # Step 1: Query observations and calculate aggregates
        aggregate_data: YearlyAggregateData = self.repository.aggregate_yearly_observations(
            station_id, year
        )
        
        # Step 2: Determine which measurements are available (non-NULL)
        measurements_available = {
            "max_temp": aggregate_data.avg_max_temp_c is not None,
            "min_temp": aggregate_data.avg_min_temp_c is not None,
            "precipitation": aggregate_data.total_precipitation_cm is not None,
        }
        
        # Step 3: Create stat object and persist
        stat_create = WeatherYearlyStatCreate(
            station_id=station_id,
            year=year,
            avg_max_temp_c=aggregate_data.avg_max_temp_c,
            avg_min_temp_c=aggregate_data.avg_min_temp_c,
            total_precipitation_cm=aggregate_data.total_precipitation_cm,
            observation_count=aggregate_data.observation_count,
        )
        yearly_stat = self.repository.upsert_yearly_stat(stat_create)
        
        # Step 4: Build summary
        summary = AggregationSummary(
            station_id=station_id,
            year=year,
            observations_processed=aggregate_data.observation_count,
            aggregation_completed_at=datetime.now(),
            measurements_available=measurements_available,
        )
        
        return yearly_stat, summary
    
    def get_yearly_stats(self, station_id: str) -> list[WeatherYearlyStat]:
        """Retrieve all yearly statistics for a station.
        
        Args:
            station_id: NOAA station identifier
            
        Returns:
            list[WeatherYearlyStat]: Yearly statistics ordered by year ascending
        """
        return list(self.repository.list_yearly_stats(station_id))
    
    def aggregate_year_range(
        self, station_id: str, start_year: int, end_year: int
    ) -> list[AggregationSummary]:
        """Calculate yearly statistics for a range of years.
        
        Aggregates observations for multiple years and stores results.
        Useful for backfilling historical data or bulk aggregation.
        
        Args:
            station_id: NOAA station identifier
            start_year: First year (inclusive)
            end_year: Last year (inclusive)
            
        Returns:
            list[AggregationSummary]: Summaries for each year processed
            
        Example:
            summaries = service.aggregate_year_range("USC00110072", 2020, 2023)
            for s in summaries:
                print(f"{s.year}: {s.observations_processed} observations")
        """
        summaries: list[AggregationSummary] = []
        for year in range(start_year, end_year + 1):
            _, summary = self.aggregate_year(station_id, year)
            summaries.append(summary)
        return summaries
