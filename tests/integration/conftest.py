import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from weather_platform.api.dependencies import get_weather_repository
from weather_platform.config.database import get_db_session
from weather_platform.main import app
from weather_platform.models.base import Base
from weather_platform.repositories.weather import SQLAlchemyWeatherRepository


@pytest.fixture(scope="session")
def integration_engine(tmp_path_factory: pytest.TempPathFactory):
    """Create a file-backed SQLite engine for integration tests."""
    database_path = tmp_path_factory.mktemp("integration-db") / "weather.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_connection(integration_engine):
    """Open a connection wrapped in an outer transaction for test isolation."""
    connection = integration_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def session_factory(db_connection):
    """Build a session factory bound to the transactional connection."""
    return sessionmaker(
        bind=db_connection,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture(scope="function")
def db_session(session_factory) -> Session:
    """Provide a direct session for assertions within integration tests."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(session_factory):
    """Provide a TestClient wired to the transactional test database."""

    app.state.metrics.reset()

    def override_weather_repository():
        session = session_factory()
        session.begin_nested()

        @event.listens_for(session, "after_transaction_end")
        def restart_savepoint(current_session, transaction):
            if transaction.nested and not transaction._parent.nested:
                current_session.begin_nested()

        try:
            yield SQLAlchemyWeatherRepository(session)
        finally:
            session.close()

    def override_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_weather_repository] = override_weather_repository
    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_weather_repository, None)
        app.dependency_overrides.pop(get_db_session, None)
