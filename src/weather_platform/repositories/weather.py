from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func, and_, extract, select, desc, asc
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from weather_platform.models.weather_observation import WeatherObservation
from weather_platform.models.weather_yearly_stat import WeatherYearlyStat
from weather_platform.repositories.base import WeatherRepository, YearlyAggregateData
from weather_platform.repositories.pagination import (
    OffsetPaginator,
    KeysetPaginator,
    OffsetPaginationParams,
    KeysetPaginationParams,
    PageResult,
)
from weather_platform.schemas.weather import WeatherObservationCreate, WeatherYearlyStatCreate


class SQLAlchemyWeatherRepository(WeatherRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def _insert_for_current_bind(self, table):
        """Return a backend-specific INSERT statement for the active session.

        The repository supports both PostgreSQL and SQLite in tests, so this
        helper selects the correct dialect insert construct before chaining the
        UPSERT clause in the calling method.
        """
        bind = self.session.get_bind()
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        if dialect_name == "sqlite":
            return sqlite_insert(table)
        return postgresql_insert(table)

    def upsert_observation(self, observation: WeatherObservationCreate) -> WeatherObservation:
        # Prefer dialect-level INSERT..ON CONFLICT when available for performance
        try:
            statement = (
                self._insert_for_current_bind(WeatherObservation)
                .values(**observation.model_dump())
                .on_conflict_do_update(
                    index_elements=[WeatherObservation.station_id, WeatherObservation.observation_date],
                    set_={
                        "max_temp_c": observation.max_temp_c,
                        "min_temp_c": observation.min_temp_c,
                        "precipitation_cm": observation.precipitation_cm,
                        "source_file": observation.source_file,
                    },
                )
            )
            self.session.execute(statement)
            self.session.commit()
            self.session.expire_all()
            return self.get_observation(observation.station_id, observation.observation_date)  # type: ignore[return-value]
        except Exception:
            # Fallback to safe ORM-style upsert if dialect insert is unsupported
            existing = self.session.scalars(
                select(WeatherObservation).where(
                    WeatherObservation.station_id == observation.station_id,
                    WeatherObservation.observation_date == observation.observation_date,
                )
            ).one_or_none()

            if existing is not None:
                existing.max_temp_c = observation.max_temp_c
                existing.min_temp_c = observation.min_temp_c
                existing.precipitation_cm = observation.precipitation_cm
                existing.source_file = observation.source_file
                self.session.add(existing)
                self.session.commit()
                return existing

            new = WeatherObservation(**observation.model_dump())
            self.session.add(new)
            self.session.commit()
            return new

    def get_observation(self, station_id: str, observation_date: date) -> WeatherObservation | None:
        statement = select(WeatherObservation).where(
            WeatherObservation.station_id == station_id,
            WeatherObservation.observation_date == observation_date,
        )
        return self.session.scalars(statement).one_or_none()

    def upsert_yearly_stat(self, stat: WeatherYearlyStatCreate) -> WeatherYearlyStat:
        try:
            values = stat.model_dump()
            statement = (
                self._insert_for_current_bind(WeatherYearlyStat)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[WeatherYearlyStat.station_id, WeatherYearlyStat.year],
                    set_={
                        "avg_max_temp_c": stat.avg_max_temp_c,
                        "avg_min_temp_c": stat.avg_min_temp_c,
                        "total_precipitation_cm": stat.total_precipitation_cm,
                        "observation_count": stat.observation_count,
                    },
                )
            )
            self.session.execute(statement)
            self.session.commit()
            self.session.expire_all()
            return self.session.scalars(
                select(WeatherYearlyStat).where(
                    WeatherYearlyStat.station_id == stat.station_id,
                    WeatherYearlyStat.year == stat.year,
                )
            ).one()
        except Exception:
            existing = self.session.scalars(
                select(WeatherYearlyStat).where(
                    WeatherYearlyStat.station_id == stat.station_id,
                    WeatherYearlyStat.year == stat.year,
                )
            ).one_or_none()

            if existing is not None:
                existing.avg_max_temp_c = stat.avg_max_temp_c
                existing.avg_min_temp_c = stat.avg_min_temp_c
                existing.total_precipitation_cm = stat.total_precipitation_cm
                existing.observation_count = stat.observation_count
                self.session.add(existing)
                self.session.commit()
                return existing

            new = WeatherYearlyStat(**stat.model_dump())
            self.session.add(new)
            self.session.commit()
            return new

    def list_yearly_stats(self, station_id: str) -> Sequence[WeatherYearlyStat]:
        statement = (
            select(WeatherYearlyStat)
            .where(WeatherYearlyStat.station_id == station_id)
            .order_by(WeatherYearlyStat.year.asc())
        )
        return self.session.scalars(statement).all()

    def aggregate_yearly_observations(
        self, station_id: str, year: int
    ) -> YearlyAggregateData:
        """Calculate yearly aggregates from observations, ignoring NULL values.
        
        Uses SQL aggregate functions to calculate:
        - avg(max_temp_c) for non-NULL records
        - avg(min_temp_c) for non-NULL records
        - sum(precipitation_cm) for non-NULL records
        - count(*) of observations in the year
        
        Args:
            station_id: NOAA station identifier
            year: Calendar year for aggregation
            
        Returns:
            YearlyAggregateData: Aggregated measurements
        """
        # Build query to aggregate observations by station/year
        # extract(year, date) requires the observation_date column
        statement = select(
            func.avg(WeatherObservation.max_temp_c).label("avg_max_temp_c"),
            func.avg(WeatherObservation.min_temp_c).label("avg_min_temp_c"),
            func.sum(WeatherObservation.precipitation_cm).label("total_precipitation_cm"),
            func.count(WeatherObservation.id).label("observation_count"),
        ).where(
            and_(
                WeatherObservation.station_id == station_id,
                extract("year", WeatherObservation.observation_date) == year,
            )
        )

        # Execute and extract results
        result = self.session.execute(statement).one()
        
        # Build result object with Decimal conversion for consistency
        return YearlyAggregateData(
            avg_max_temp_c=Decimal(str(result.avg_max_temp_c)) if result.avg_max_temp_c is not None else None,
            avg_min_temp_c=Decimal(str(result.avg_min_temp_c)) if result.avg_min_temp_c is not None else None,
            total_precipitation_cm=Decimal(str(result.total_precipitation_cm)) if result.total_precipitation_cm is not None else None,
            observation_count=result.observation_count or 0,
        )

    def query_observations(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[Sequence[WeatherObservation], int]:
        """Query observations with optional filtering and pagination.
        
        Builds a filtered query for observations and returns both the paginated
        results and the total count of matching records. Ordering is by date descending.
        
        Args:
            skip: Number of records to skip for pagination
            limit: Maximum records per page
            station_id: Optional filter by station
            start_date: Optional minimum observation date
            end_date: Optional maximum observation date
            
        Returns:
            tuple[Sequence[WeatherObservation], int]: (observations_page, total_count)
        """
        # Build base query with optional filters
        filters = []
        if station_id is not None:
            filters.append(WeatherObservation.station_id == station_id)
        if start_date is not None:
            filters.append(WeatherObservation.observation_date >= start_date)
        if end_date is not None:
            filters.append(WeatherObservation.observation_date <= end_date)

        # Count total matching records
        count_statement = select(func.count()).select_from(WeatherObservation)
        if filters:
            count_statement = count_statement.where(and_(*filters))
        total_count = self.session.scalar(count_statement) or 0

        # Fetch paginated results ordered by date descending
        data_statement = select(WeatherObservation).order_by(
            desc(WeatherObservation.observation_date)
        )
        if filters:
            data_statement = data_statement.where(and_(*filters))
        data_statement = data_statement.offset(skip).limit(limit)

        observations = self.session.scalars(data_statement).all()
        return observations, total_count

    def query_yearly_stats(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> tuple[Sequence[WeatherYearlyStat], int]:
        """Query yearly statistics with optional filtering and pagination.
        
        Builds a filtered query for yearly stats and returns both the paginated
        results and the total count of matching records. Ordering is by year descending.
        
        Args:
            skip: Number of records to skip for pagination
            limit: Maximum records per page
            station_id: Optional filter by station
            start_year: Optional minimum year (inclusive)
            end_year: Optional maximum year (inclusive)
            
        Returns:
            tuple[Sequence[WeatherYearlyStat], int]: (stats_page, total_count)
        """
        # Build base query with optional filters
        filters = []
        if station_id is not None:
            filters.append(WeatherYearlyStat.station_id == station_id)
        if start_year is not None:
            filters.append(WeatherYearlyStat.year >= start_year)
        if end_year is not None:
            filters.append(WeatherYearlyStat.year <= end_year)

        # Count total matching records
        count_statement = select(func.count()).select_from(WeatherYearlyStat)
        if filters:
            count_statement = count_statement.where(and_(*filters))
        total_count = self.session.scalar(count_statement) or 0

        # Fetch paginated results ordered by year descending
        data_statement = select(WeatherYearlyStat).order_by(
            desc(WeatherYearlyStat.year)
        )
        if filters:
            data_statement = data_statement.where(and_(*filters))
        data_statement = data_statement.offset(skip).limit(limit)

        yearly_stats = self.session.scalars(data_statement).all()
        return yearly_stats, total_count


    

    # ========== Optimized Query Methods (Pagination-Aware) ==========
    
    def query_observations_keyset(
        self,
        limit: int = 100,
        cursor: str | None = None,
        station_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PageResult[WeatherObservation]:
        """Query observations using keyset (cursor-based) pagination.
        
        More efficient than offset pagination for large datasets.
        Uses the previous page's last row as a starting point instead of OFFSET.
        
        Example:
            # First page
            result = repo.query_observations_keyset(limit=100)
            
            # Next page using cursor from previous result
            if result.has_next:
                result = repo.query_observations_keyset(
                    limit=100,
                    cursor=result.cursor
                )
        
        Args:
            limit: Records per page (max 10000)
            cursor: Opaque cursor from previous page (None for first page)
            station_id: Optional filter by station
            start_date: Optional minimum observation date
            end_date: Optional maximum observation date
            
        Returns:
            PageResult with items, has_next flag, and next cursor
        """
        # Build base statement with filters
        filters = []
        if station_id is not None:
            filters.append(WeatherObservation.station_id == station_id)
        if start_date is not None:
            filters.append(WeatherObservation.observation_date >= start_date)
        if end_date is not None:
            filters.append(WeatherObservation.observation_date <= end_date)

        def base_query_fn():
            stmt = select(WeatherObservation).order_by(
                desc(WeatherObservation.observation_date),
                WeatherObservation.id,
            )
            if filters:
                stmt = stmt.where(and_(*filters))
            return stmt, WeatherObservation

        params = KeysetPaginationParams(limit=limit, cursor=cursor)
        paginator = KeysetPaginator(
            self.session,
            keyset_columns=[
                desc(WeatherObservation.observation_date),
                WeatherObservation.id,
            ],
        )
        return paginator.paginate(base_query_fn, params)

    def query_yearly_stats_keyset(
        self,
        limit: int = 100,
        cursor: str | None = None,
        station_id: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> PageResult[WeatherYearlyStat]:
        """Query yearly stats using keyset (cursor-based) pagination.
        
        More efficient than offset pagination for large datasets.
        
        Args:
            limit: Records per page (max 10000)
            cursor: Opaque cursor from previous page (None for first page)
            station_id: Optional filter by station
            start_year: Optional minimum year (inclusive)
            end_year: Optional maximum year (inclusive)
            
        Returns:
            PageResult with items, has_next flag, and next cursor
        """
        filters = []
        if station_id is not None:
            filters.append(WeatherYearlyStat.station_id == station_id)
        if start_year is not None:
            filters.append(WeatherYearlyStat.year >= start_year)
        if end_year is not None:
            filters.append(WeatherYearlyStat.year <= end_year)

        def base_query_fn():
            stmt = select(WeatherYearlyStat).order_by(
                desc(WeatherYearlyStat.year),
                WeatherYearlyStat.id,
            )
            if filters:
                stmt = stmt.where(and_(*filters))
            return stmt, WeatherYearlyStat

        params = KeysetPaginationParams(limit=limit, cursor=cursor)
        paginator = KeysetPaginator(
            self.session,
            keyset_columns=[
                desc(WeatherYearlyStat.year),
                WeatherYearlyStat.id,
            ],
        )
        return paginator.paginate(base_query_fn, params)

    def query_observations_optimized(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        use_explain: bool = False,
    ) -> tuple[Sequence[WeatherObservation], int, dict[str, str] | None]:
        """Query observations with optional EXPLAIN ANALYZE for query tuning.
        
        This method uses offset pagination (traditional) but provides
        EXPLAIN output for performance analysis and index validation.
        
        Args:
            skip: Number of records to skip
            limit: Records per page
            station_id: Optional filter by station
            start_date: Optional minimum observation date
            end_date: Optional maximum observation date
            use_explain: If True, include EXPLAIN ANALYZE in result (PostgreSQL only)
            
        Returns:
            tuple of (observations, total_count, explain_dict)
            where explain_dict is None or contains {"optimization_tip": "..."}
        """
        from weather_platform.repositories.query_optimizer import ExplainAnalyzer

        filters = []
        if station_id is not None:
            filters.append(WeatherObservation.station_id == station_id)
        if start_date is not None:
            filters.append(WeatherObservation.observation_date >= start_date)
        if end_date is not None:
            filters.append(WeatherObservation.observation_date <= end_date)

        # Build count statement
        count_stmt = select(func.count()).select_from(WeatherObservation)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total_count = self.session.scalar(count_stmt) or 0

        # Build data statement
        data_stmt = select(WeatherObservation).order_by(
            desc(WeatherObservation.observation_date)
        )
        if filters:
            data_stmt = data_stmt.where(and_(*filters))
        data_stmt = data_stmt.offset(skip).limit(limit)

        observations = self.session.scalars(data_stmt).all()

        # Optional: run EXPLAIN ANALYZE for query optimization insights
        explain_dict = None
        if use_explain:
            analyzer = ExplainAnalyzer(self.session, dialect="postgresql")
            result = analyzer.analyze(data_stmt)
            if result:
                explain_dict = {
                    "planning_time_ms": str(result.planning_time_ms),
                    "execution_time_ms": str(result.execution_time_ms),
                    "is_efficient": str(result.is_efficient),
                    "optimization_needed": result.optimization_needed or "None",
                }

        return observations, total_count, explain_dict

    def query_yearly_stats_optimized(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        use_explain: bool = False,
    ) -> tuple[Sequence[WeatherYearlyStat], int, dict[str, str] | None]:
        """Query yearly stats with optional EXPLAIN ANALYZE for query tuning.
        
        Args:
            skip: Number of records to skip
            limit: Records per page
            station_id: Optional filter by station
            start_year: Optional minimum year (inclusive)
            end_year: Optional maximum year (inclusive)
            use_explain: If True, include EXPLAIN ANALYZE in result (PostgreSQL only)
            
        Returns:
            tuple of (stats, total_count, explain_dict)
        """
        from weather_platform.repositories.query_optimizer import ExplainAnalyzer

        filters = []
        if station_id is not None:
            filters.append(WeatherYearlyStat.station_id == station_id)
        if start_year is not None:
            filters.append(WeatherYearlyStat.year >= start_year)
        if end_year is not None:
            filters.append(WeatherYearlyStat.year <= end_year)

        # Build count statement
        count_stmt = select(func.count()).select_from(WeatherYearlyStat)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total_count = self.session.scalar(count_stmt) or 0

        # Build data statement
        data_stmt = select(WeatherYearlyStat).order_by(
            desc(WeatherYearlyStat.year)
        )
        if filters:
            data_stmt = data_stmt.where(and_(*filters))
        data_stmt = data_stmt.offset(skip).limit(limit)

        yearly_stats = self.session.scalars(data_stmt).all()

        # Optional: run EXPLAIN ANALYZE
        explain_dict = None
        if use_explain:
            analyzer = ExplainAnalyzer(self.session, dialect="postgresql")
            result = analyzer.analyze(data_stmt)
            if result:
                explain_dict = {
                    "planning_time_ms": str(result.planning_time_ms),
                    "execution_time_ms": str(result.execution_time_ms),
                    "is_efficient": str(result.is_efficient),
                    "optimization_needed": result.optimization_needed or "None",
                }

        return yearly_stats, total_count, explain_dict


# Module-level convenience alias so callers importing `WeatherRepository`
# from this module (tests or older code) receive the concrete implementation.
WeatherRepository = SQLAlchemyWeatherRepository
