"""Database configuration and connection management.

This module handles SQLAlchemy engine creation, session management, and
provides dependency injection helpers for FastAPI and CLI use.
"""
from collections.abc import Generator
import contextlib
import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from weather_platform.config.settings import get_settings


class EngineFactory:
    """Factory to create SQLAlchemy Engine instances.

    Implements a small Open/Closed extension point so additional
    database backends can be supported without modifying call sites.
    
    Attributes:
        url: Database connection URL (e.g., postgresql://...)
        echo: Whether to log all SQL statements (useful for debugging)
    """

    def __init__(self, url: str, echo: bool = False) -> None:
        """Initialize factory with database connection parameters.
        
        Args:
            url: SQLAlchemy database URL
            echo: If True, log all SQL statements to stdout
        """
        self.url = url
        self.echo = echo

    def create(self) -> Engine:
        """Create and return a configured SQLAlchemy Engine.
        
        Returns:
            Engine: Configured SQLAlchemy engine with connection pooling
        """
        return create_engine(self.url, echo=self.echo, pool_pre_ping=True)


class UnitOfWork:
    """Unit of Work style session manager for transaction control.

    Implements context manager protocol for transactional scope. Use to wrap
    database operations that should succeed or fail atomically.
    
    Can be used in two ways:
    1. Context manager: `with UnitOfWork(...) as uow: ...`
    2. FastAPI dependency: `def endpoint(uow: UnitOfWork = Depends(get_uow))`
    
    Attributes:
        session: SQLAlchemy Session instance
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """Initialize with a session factory.
        
        Args:
            session_factory: SQLAlchemy sessionmaker for creating sessions
        """
        self._session_factory = session_factory
        self.session: Optional[Session] = None

    def __enter__(self) -> "UnitOfWork":
        """Enter context manager, creating a new session.
        
        Returns:
            UnitOfWork: Self for use in context manager
        """
        self.session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit context manager, committing or rolling back transaction.
        
        Commits if no exception occurred, rolls back otherwise.
        Always closes the session.
        
        Args:
            exc_type: Exception type if error occurred
            exc: Exception instance if error occurred
            tb: Exception traceback if error occurred
        """
        try:
            if exc is None:
                # No exception: commit the transaction
                self.session.commit()
            else:
                # Exception occurred: rollback to maintain consistency
                self.session.rollback()
        finally:
            # Always close the session, even if commit/rollback fails
            self.session.close()

    def commit(self) -> None:
        """Explicitly commit the current transaction.
        
        Raises:
            RuntimeError: If session not yet started
        """
        if self.session is None:
            raise RuntimeError("session not started")
        self.session.commit()

    def rollback(self) -> None:
        """Explicitly rollback the current transaction.
        
        Raises:
            RuntimeError: If session not yet started
        """
        if self.session is None:
            raise RuntimeError("session not started")
        self.session.rollback()


def configure_engine_and_session(settings=None):
    """Create engine and session factory from settings.
    
    Factory function for setting up SQLAlchemy engine and session factory
    with appropriate configuration from settings.
    
    Args:
        settings: Settings instance with database_url and alchemy_echo.
                 If None, loads via get_settings().
    
    Returns:
        tuple[Engine, sessionmaker]: Configured engine and session factory
    """
    if settings is None:
        settings = get_settings()

    # Create engine via factory
    factory = EngineFactory(settings.database_url, echo=settings.alchemy_echo)
    engine = factory.create()
    
    # Configure session factory with recommended settings for ORM
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,  # Don't flush automatically, explicit control
        autocommit=False,  # Require explicit commit
        expire_on_commit=False,  # Keep objects loaded after commit
    )
    return engine, SessionLocal


# Module-level singletons for convenience
# Applications may reconfigure by calling `configure_engine_and_session` with other settings
settings = get_settings()
engine, SessionLocal = configure_engine_and_session(settings)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session for a request.
    
    Yields:
        Session: SQLAlchemy session for request duration
        
    Example:
        @app.get("/observations")
        def list_observations(session: Session = Depends(get_db_session)):
            return session.query(WeatherObservation).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_uow() -> Generator[UnitOfWork, None, None]:
    """FastAPI dependency that yields a UnitOfWork for a request.
    
    Yields a UnitOfWork (context manager) for request lifetime. Automatically
    commits on success or rolls back on exception.
    
    Yields:
        UnitOfWork: Transaction-scoped session wrapper
        
    Example:
        @app.post("/observations")
        def create_observation(obs: WeatherObservationCreate, uow: UnitOfWork = Depends(get_uow)):
            repository = WeatherRepository(uow.session)
            return repository.upsert_observation(obs)
    """
    with UnitOfWork(SessionLocal) as uow:
        yield uow

    Usage in a route: `uow: UnitOfWork = Depends(get_uow)` and then use
    `uow.session` inside handlers/services. The UnitOfWork commits on
    exit when used as a context manager; the FastAPI dependency will
    commit if no exception is raised.
    """
    uow = UnitOfWork(SessionLocal)
    try:
        # start the session
        uow.__enter__()
        yield uow
        # commit handled in __exit__ below
    except Exception:
        uow.__exit__(None, None, None)
        raise
    else:
        uow.__exit__(None, None, None)
