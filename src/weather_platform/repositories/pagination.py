"""Pagination abstractions for query optimization.

This module provides flexible, EXPLAIN-friendly pagination strategies
that remain isolated from business logic. Repositories can choose between
offset-based (simple, suitable for small datasets) and keyset-based
(efficient for large datasets or real-time feeds).

Design principles:
- Keep pagination logic separate from filtering/business logic
- Provide explain-plan friendly SQL (use specific column ordering)
- Support dialect-specific query optimization
- Allow consumers to remain agnostic to pagination strategy

Keyset (Cursor-Based) Pagination Benefits:
- Efficient for large datasets (no full table scans)
- Handles concurrent inserts/deletions gracefully
- Enables real-time feeds without cursor invalidation
- Suitable for "load more" UI patterns
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

from sqlalchemy import ColumnElement, and_, desc, select
from sqlalchemy.orm import Session

T = TypeVar("T")


@dataclass
class OffsetPaginationParams:
    """Parameters for offset-based pagination."""

    skip: int = 0
    limit: int = 100

    def validate(self, max_limit: int = 10000) -> None:
        """Validate and normalize pagination parameters.
        
        Args:
            max_limit: Maximum allowed limit to prevent resource exhaustion
            
        Raises:
            ValueError: If parameters are invalid
        """
        if self.skip < 0:
            raise ValueError("skip must be >= 0")
        if self.limit < 1 or self.limit > max_limit:
            raise ValueError(f"limit must be between 1 and {max_limit}")


@dataclass
class KeysetPaginationParams:
    """Parameters for keyset (cursor-based) pagination.
    
    Keyset pagination uses the last row's key values to fetch the next page,
    avoiding expensive OFFSET operations. This is more efficient for large
    datasets and real-time scenarios.
    
    Example flow:
        1. GET /observations?limit=100
           Returns rows with keyset_cursor={id: 1000, observation_date: '2020-01-15'}
        
        2. GET /observations?limit=100&cursor=<encoded_cursor>
           Returns next 100 rows starting after the cursor position
    """

    limit: int = 100
    cursor: str | None = None  # Opaque cursor from previous page's last row

    def validate(self, max_limit: int = 10000) -> None:
        """Validate pagination parameters.
        
        Args:
            max_limit: Maximum allowed limit to prevent resource exhaustion
            
        Raises:
            ValueError: If parameters are invalid
        """
        if self.limit < 1 or self.limit > max_limit:
            raise ValueError(f"limit must be between 1 and {max_limit}")


@dataclass
class PageResult(Generic[T]):
    """Result from a pagination query."""

    items: Sequence[T]
    total_count: int | None  # None for keyset pagination (unknown)
    has_next: bool = False  # For keyset: True if more items available
    cursor: str | None = None  # For keyset: position for next query


class PaginationStrategy(ABC, Generic[T]):
    """Base class for pagination strategies.
    
    Implementations should:
    1. Generate EXPLAIN-friendly SQL queries
    2. Return both items and cursor/count information
    3. Keep pagination logic independent of filtering
    """

    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def paginate(
        self,
        query_callable,
        params: OffsetPaginationParams | KeysetPaginationParams,
    ) -> PageResult[T]:
        """Execute a paginated query.
        
        Args:
            query_callable: Function returning base SELECT statement (filters already applied)
            params: Pagination parameters
            
        Returns:
            PageResult with items, counts/cursors, and pagination metadata
        """
        pass


class OffsetPaginator(PaginationStrategy[T]):
    """Traditional offset-based pagination.
    
    Suitable for small to medium datasets. For large datasets or
    high-frequency queries, consider KeysetPaginator.
    
    SQL Pattern:
        SELECT * FROM table WHERE (filters) ORDER BY (columns)
        OFFSET ? LIMIT ?
    """

    def paginate(
        self,
        query_callable,
        params: OffsetPaginationParams,
    ) -> PageResult[T]:
        """Execute offset-based pagination.
        
        Executes the full query twice:
        1. COUNT(*) to determine total records (expensive for large tables)
        2. SELECT with OFFSET/LIMIT for current page
        
        Args:
            query_callable: Function(stmt) -> (base_select_stmt, count_select_stmt, Model)
                Should return tuple of:
                - base SELECT statement with filters, no pagination
                - COUNT statement for total
                - Model class for type info
            params: OffsetPaginationParams
            
        Returns:
            PageResult with items and total_count
        """
        params.validate()

        base_stmt, count_stmt, model_class = query_callable()

        # Fetch total count (single pass through filter predicate)
        total_count = self.session.scalar(count_stmt) or 0

        # Fetch paginated results
        paginated_stmt = base_stmt.offset(params.skip).limit(params.limit)

        # Use EXPLAIN to validate query plan if needed
        items = self.session.scalars(paginated_stmt).all()

        return PageResult(
            items=items,
            total_count=total_count,
            has_next=(params.skip + len(items)) < total_count,
        )


class KeysetPaginator(PaginationStrategy[T]):
    """Keyset (cursor-based) pagination for efficient large-dataset queries.
    
    Keyset pagination avoids OFFSET by using the previous page's last row
    as a starting point. This is much faster for large datasets and handles
    concurrent modifications gracefully.
    
    SQL Pattern:
        -- First page
        SELECT * FROM table WHERE (filters) ORDER BY (keyset_columns)
        LIMIT ?
        
        -- Next page (cursor = {col1: val1, col2: val2, ...})
        SELECT * FROM table WHERE (filters)
          AND (col1, col2, ...) > (?, ?, ...)  -- keyset comparison
        ORDER BY (keyset_columns) LIMIT ?
    
    Requirements:
    - Keyset columns must be unique or include PK
    - ORDER BY must match keyset ordering for consistency
    """

    def __init__(self, session: Session, keyset_columns: list[ColumnElement]):
        """Initialize keyset paginator.
        
        Args:
            session: SQLAlchemy session
            keyset_columns: Ordered list of columns for keyset comparison
                Example: [WeatherObservation.observation_date.desc(), WeatherObservation.id]
        """
        super().__init__(session)
        self.keyset_columns = keyset_columns

    def paginate(
        self,
        query_callable,
        params: KeysetPaginationParams,
    ) -> PageResult[T]:
        """Execute keyset-based pagination.
        
        Args:
            query_callable: Function() -> (base_select_stmt, Model)
                Should return:
                - base SELECT with filters and ORDER BY matching keyset_columns
                - Model class for type info
            params: KeysetPaginationParams with cursor (optional)
            
        Returns:
            PageResult with items, has_next flag, and cursor for next page
        """
        params.validate()

        base_stmt, model_class = query_callable()

        # For initial request (no cursor), fetch limit+1 to detect has_next
        fetch_count = params.limit + 1

        if params.cursor:
            # Decode cursor and add keyset condition
            keyset_values = self._decode_cursor(params.cursor)
            base_stmt = self._add_keyset_filter(base_stmt, keyset_values)

        result_rows = self.session.scalars(base_stmt.limit(fetch_count)).all()

        has_next = len(result_rows) > params.limit
        items = result_rows[: params.limit]

        next_cursor = None
        if has_next and items:
            next_cursor = self._encode_cursor(items[-1])

        return PageResult(
            items=items,
            total_count=None,  # Keyset pagination doesn't provide total
            has_next=has_next,
            cursor=next_cursor,
        )

    def _encode_cursor(self, row) -> str:
        """Encode row's keyset columns into an opaque cursor string.
        
        Args:
            row: Model instance
            
        Returns:
            Base64-encoded cursor string
        """
        import base64
        import json

        values = []
        for col in self.keyset_columns:
            # If column is an ordering expression (e.g. desc(col)), get the underlying element
            base = getattr(col, "element", col)
            col_name = getattr(base, "key", getattr(base, "name", str(base)))
            col_value = getattr(row, col_name, None)
            # Serialize to string for JSON
            values.append(str(col_value))

        cursor_json = json.dumps(values)
        return base64.b64encode(cursor_json.encode()).decode()

    def _decode_cursor(self, cursor: str) -> list:
        """Decode opaque cursor string back to keyset values.
        
        Args:
            cursor: Base64-encoded cursor from _encode_cursor
            
        Returns:
            List of keyset column values
            
        Raises:
            ValueError: If cursor is malformed
        """
        import base64
        import json

        try:
            cursor_json = base64.b64decode(cursor.encode()).decode()
            return json.loads(cursor_json)
        except Exception as e:
            raise ValueError(f"Invalid cursor format: {e}")

    def _add_keyset_filter(self, stmt, keyset_values: list):
        """Add keyset comparison clause to WHERE condition with type coercion.

        Creates a lexicographic comparison that respects SQLAlchemy column types
        by coercing decoded cursor values to the underlying Python types before
        building comparison expressions.
        """
        from sqlalchemy import or_, and_
        from datetime import date as _date
        from decimal import Decimal as _Decimal
        from sqlalchemy.sql.sqltypes import Date as _SQLDate, Integer as _SQLInteger, Numeric as _SQLNumeric

        # Normalize columns (strip ordering wrappers like desc()) and determine comparison direction
        comparison_columns = []
        directions = []  # 'gt' for ascending, 'lt' for descending
        for col in self.keyset_columns:
            base = getattr(col, "element", col)
            comparison_columns.append(base)
            # Heuristic: if ordering expression contains DESC, treat as descending
            if "DESC" in str(col).upper():
                directions.append("lt")
            else:
                directions.append("gt")

        # Build lexicographic comparison:
        # (c1 op1 v1) OR (c1 == v1 AND c2 op2 v2) OR (...)
        if len(comparison_columns) != len(keyset_values):
            raise ValueError("cursor length does not match keyset columns")

        def _coerce_value(raw_val, column):
            col_type = getattr(column, "type", None)
            # If value already appears to be the correct python type, return as-is
            if raw_val is None:
                return None
            try:
                # Dates are encoded as ISO strings in the cursor
                if isinstance(col_type, _SQLDate):
                    return _date.fromisoformat(raw_val) if isinstance(raw_val, str) else raw_val
                if isinstance(col_type, _SQLInteger):
                    return int(raw_val)
                if isinstance(col_type, _SQLNumeric):
                    return _Decimal(str(raw_val))
            except Exception:
                # Fall back to the raw value on any conversion error
                return raw_val
            return raw_val

        conditions = []
        for i in range(len(comparison_columns)):
            # Build equality prefix using coerced values
            left_eq = [comparison_columns[j] == _coerce_value(keyset_values[j], comparison_columns[j]) for j in range(i)]
            op_col = comparison_columns[i]
            op_val = _coerce_value(keyset_values[i], op_col)
            if directions[i] == "lt":
                cmp_expr = op_col < op_val
            else:
                cmp_expr = op_col > op_val

            if left_eq:
                conditions.append(and_(*left_eq, cmp_expr))
            else:
                conditions.append(cmp_expr)

        keyset_condition = or_(*conditions)
        return stmt.where(keyset_condition)
