"""Query optimization and EXPLAIN analysis tools.

This module provides utilities for understanding and optimizing database queries
while keeping performance concerns isolated in the repository layer.

Features:
- EXPLAIN ANALYZE output parsing for readability
- Query cost analysis for optimization decisions
- Index usage verification
- Batch query planning for representative cases
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class IndexUsageStatus(Enum):
    """Status of index usage in a query plan."""

    USED = "used"
    UNUSED = "unused"
    SEQUENTIAL_SCAN = "sequential_scan"
    INDEX_ONLY_SCAN = "index_only_scan"


@dataclass
class QueryPlanNode:
    """Represents a single node in a query execution plan."""

    node_type: str
    relation_name: str | None
    index_name: str | None
    startup_cost: float
    total_cost: float
    actual_rows: int | None
    index_used: IndexUsageStatus

    @property
    def cost_ratio(self) -> float:
        """Ratio of actual_rows to estimated cost (lower is better for planning)."""
        if self.total_cost == 0:
            return 0.0
        return (self.actual_rows or 0) / self.total_cost


@dataclass
class ExplainAnalysisResult:
    """Result from EXPLAIN ANALYZE query execution."""

    query: str
    planning_time_ms: float
    execution_time_ms: float
    total_rows_scanned: int
    root_node: QueryPlanNode
    sequential_scans: list[QueryPlanNode]
    index_scans: list[QueryPlanNode]
    index_only_scans: list[QueryPlanNode]

    @property
    def is_efficient(self) -> bool:
        """Quick heuristic: efficient if no sequential scans and reasonable cost."""
        return len(self.sequential_scans) == 0 and self.planning_time_ms < 100

    @property
    def optimization_needed(self) -> str | None:
        """Identify likely optimization opportunity."""
        if self.sequential_scans:
            return f"Sequential scan on {self.sequential_scans[0].relation_name}; consider index on filter columns"
        if self.execution_time_ms > 1000:
            return "Slow query execution; verify index selectivity or join order"
        if self.planning_time_ms > 50:
            return "High planning time; simplify query or use explicit JOINs"
        return None


class ExplainAnalyzer:
    """Utility for analyzing query plans with EXPLAIN ANALYZE.
    
    PostgreSQL-specific. Requires appropriate database permissions.
    
    Example:
        analyzer = ExplainAnalyzer(session, dialect="postgresql")
        stmt = select(WeatherObservation).where(
            WeatherObservation.station_id == "USC00110072",
            WeatherObservation.observation_date >= date(2020, 1, 1),
        )
        result = analyzer.analyze(stmt)
        print(f"Query efficient: {result.is_efficient}")
        if result.optimization_needed:
            print(f"Optimization tip: {result.optimization_needed}")
    """

    def __init__(self, session: Session, dialect: str = "postgresql"):
        """Initialize analyzer for a specific database dialect.
        
        Args:
            session: SQLAlchemy session
            dialect: Database dialect ("postgresql", "sqlite", etc.)
        """
        self.session = session
        self.dialect = dialect

    def analyze(self, statement) -> ExplainAnalysisResult | None:
        """Execute EXPLAIN ANALYZE and parse the results.
        
        Args:
            statement: SQLAlchemy select() statement to analyze
            
        Returns:
            ExplainAnalysisResult with plan details, or None if dialect unsupported
        """
        if self.dialect != "postgresql":
            return None

        compiled = str(
            statement.compile(compile_kwargs={"literal_binds": False})
        ).replace("\n", " ")
        explain_query = f"EXPLAIN ANALYZE {compiled}"

        try:
            result = self.session.execute(text(explain_query))
            lines = [row[0] for row in result]
            return self._parse_explain_output(compiled, lines)
        except Exception as e:
            print(f"Failed to execute EXPLAIN ANALYZE: {e}")
            return None

    def _parse_explain_output(self, original_query: str, lines: list[str]) -> ExplainAnalysisResult:
        """Parse PostgreSQL EXPLAIN ANALYZE output.
        
        This is a simplified parser. For production use, consider using
        explain package or pganalyze for detailed plan analysis.
        
        Args:
            original_query: The SQL query that was explained
            lines: Lines of EXPLAIN ANALYZE output
            
        Returns:
            Parsed ExplainAnalysisResult
        """
        planning_time = 0.0
        execution_time = 0.0
        sequential_scans: list[QueryPlanNode] = []
        index_scans: list[QueryPlanNode] = []
        index_only_scans: list[QueryPlanNode] = []

        for line in lines:
            line = line.strip()
            if "Planning Time:" in line:
                planning_time = float(line.split()[-2])
            elif "Execution Time:" in line:
                execution_time = float(line.split()[-2])
            elif "Seq Scan" in line:
                sequential_scans.append(
                    self._extract_plan_node(line, IndexUsageStatus.SEQUENTIAL_SCAN)
                )
            elif "Index Scan" in line and "Index Only" not in line:
                index_scans.append(
                    self._extract_plan_node(line, IndexUsageStatus.USED)
                )
            elif "Index Only Scan" in line:
                index_only_scans.append(
                    self._extract_plan_node(line, IndexUsageStatus.INDEX_ONLY_SCAN)
                )

        # Create a minimal root node for the result
        root_node = QueryPlanNode(
            node_type="Plan",
            relation_name=None,
            index_name=None,
            startup_cost=0.0,
            total_cost=0.0,
            actual_rows=None,
            index_used=IndexUsageStatus.USED,
        )

        total_rows = sum(
            (n.actual_rows or 0)
            for n in [*sequential_scans, *index_scans, *index_only_scans]
        )

        return ExplainAnalysisResult(
            query=original_query,
            planning_time_ms=planning_time,
            execution_time_ms=execution_time,
            total_rows_scanned=total_rows,
            root_node=root_node,
            sequential_scans=sequential_scans,
            index_scans=index_scans,
            index_only_scans=index_only_scans,
        )

    def _extract_plan_node(self, line: str, status: IndexUsageStatus) -> QueryPlanNode:
        """Extract a single plan node from EXPLAIN output line.
        
        Args:
            line: A line from EXPLAIN ANALYZE output
            status: The type of scan detected
            
        Returns:
            QueryPlanNode with extracted information
        """
        # Simplified extraction; production parsers are more robust
        relation_name = None
        index_name = None

        if " on " in line:
            parts = line.split(" on ")
            if len(parts) > 1:
                relation_name = parts[1].split()[0]

        if "using" in line.lower():
            parts = line.split("using")
            if len(parts) > 1:
                index_name = parts[1].split()[0]

        return QueryPlanNode(
            node_type=status.value,
            relation_name=relation_name,
            index_name=index_name,
            startup_cost=0.0,
            total_cost=0.0,
            actual_rows=None,
            index_used=status,
        )


class QueryPlanCache:
    """Cache query plans to avoid repeated EXPLAIN calls during development.
    
    Useful for batch analysis of multiple query patterns without hitting
    the database repeatedly.
    """

    def __init__(self):
        """Initialize an empty plan cache."""
        self.cache: dict[str, ExplainAnalysisResult] = {}

    def get(self, query_hash: str) -> ExplainAnalysisResult | None:
        """Retrieve a cached plan.
        
        Args:
            query_hash: Hash of the query (use hash() or hashlib.sha256)
            
        Returns:
            Cached ExplainAnalysisResult or None
        """
        return self.cache.get(query_hash)

    def put(self, query_hash: str, result: ExplainAnalysisResult) -> None:
        """Store a plan in the cache.
        
        Args:
            query_hash: Hash of the query
            result: ExplainAnalysisResult to cache
        """
        self.cache[query_hash] = result

    def clear(self) -> None:
        """Clear all cached plans."""
        self.cache.clear()
