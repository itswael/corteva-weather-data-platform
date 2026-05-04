import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from weather_platform.main import app


@pytest.fixture(scope="function")
def client(reset_database):
    """Provide a TestClient with a clean database for integration tests.
    
    This fixture:
    - Depends on reset_database to ensure a clean schema
    - Resets app metrics for each test
    - Returns a TestClient wired to the app
    
    The fixture relies on the root conftest's reset_database fixture
    (which resets the in-memory SQLite database) and overrides app.state.metrics
    to start fresh for each test.
    """
    # Reset app metrics before each test
    app.state.metrics.reset()
    
    # Create and return a TestClient
    tc = TestClient(app)
    yield tc
    tc.close()
