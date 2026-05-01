import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from weather_platform.main import app
from weather_platform.models.base import Base


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Fixture providing a clean SQLite database session for each test.
    
    Creates fresh tables for each test using in-memory SQLite
    and cleans up after.
    
    Yields:
        Session: SQLAlchemy session for test operations
    """
    # Create in-memory SQLite engine for testing
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session factory and session
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    
    yield session
    
    # Cleanup: rollback and close
    session.rollback()
    session.close()
