import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Set test environment BEFORE importing weather_platform
os.environ.setdefault("APP_ENV", "test")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from weather_platform.main import app
from weather_platform.models.base import Base
from weather_platform.config.database import engine as app_engine, SessionLocal as AppSessionLocal


@pytest.fixture(autouse=True)
def reset_database() -> None:
    """Fixture to reset the database before each test.
    
    This ensures that every test starts with a clean database state by dropping
    and recreating all tables. This fixture:
    - Runs automatically before each test (autouse=True)
    - Uses an in-memory SQLite database with StaticPool for test isolation
    - Disposes all pooled connections before resetting to ensure clean state
    - Works with local conftest.py files that may override other fixtures
    
    The local conftest in tests/integration/ depends on this fixture to ensure
    that both client and db_session fixtures operate on the same clean database.
    """
    # Dispose of all connections to clear any pooled connections
    app_engine.dispose()
    
    # Drop and recreate schema to ensure isolation
    Base.metadata.drop_all(bind=app_engine)
    Base.metadata.create_all(bind=app_engine)
    yield


@pytest.fixture()
def client(reset_database) -> TestClient:
    """TestClient fixture for making HTTP requests to the app."""
    # Ensure database is fresh before creating client
    # Create a fresh TestClient for each test to avoid session carryover
    tc = TestClient(app)
    yield tc
    # Explicitly close the client after the test
    tc.close()


@pytest.fixture(scope="function")
def db_session(reset_database) -> Session:
    """Fixture providing a clean SQLite database session for each test.
    
    Creates a session for direct database access in tests.
    
    Yields:
        Session: SQLAlchemy session for test operations
    """
    # Use the application's SessionLocal so both app and tests share the same connection
    session = AppSessionLocal()
    
    try:
        yield session
    finally:
        # Cleanup: rollback and close
        session.rollback()
        session.close()
