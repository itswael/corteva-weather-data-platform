from collections.abc import Generator
import contextlib
import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from weather_platform.config.settings import get_settings


class EngineFactory:
    """Factory to create SQLAlchemy Engine instances.

    This implements a small Open/Closed extension point so additional
    database backends can be supported without modifying call sites.
    """

    def __init__(self, url: str, echo: bool = False) -> None:
        self.url = url
        self.echo = echo

    def create(self) -> Engine:
        # Special-case in-memory SQLite: use a StaticPool and disable same-thread
        # checks so multiple connections (TestClient, test fixtures) see the
        # same in-memory database instance.
        if isinstance(self.url, str) and "sqlite" in self.url and ":memory:" in self.url:
            return create_engine(
                self.url,
                echo=self.echo,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        return create_engine(self.url, echo=self.echo, pool_pre_ping=True)


class UnitOfWork:
    """Unit of Work style session manager.

    Use as a context manager for transactional work, or rely on the
    FastAPI dependency `get_uow` which yields a `UnitOfWork` for a
    single request lifecycle.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self.session: Optional[Session] = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()

    # explicit helpers for service code
    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("session not started")
        self.session.commit()

    def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("session not started")
        self.session.rollback()


def configure_engine_and_session(settings=None):
    """Create engine and session factory from settings.

    Returns (engine, SessionLocal).
    """
    if settings is None:
        settings = get_settings()

    factory = EngineFactory(settings.database_dsn, echo=settings.alchemy_echo)
    engine = factory.create()
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return engine, SessionLocal


# Module-level singletons for convenience; applications may reconfigure
# by calling `configure_engine_and_session` with other settings.
settings = get_settings()
engine, SessionLocal = configure_engine_and_session(settings)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_uow() -> Generator[UnitOfWork, None, None]:
    """FastAPI-friendly dependency that yields a UnitOfWork for a request.

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
