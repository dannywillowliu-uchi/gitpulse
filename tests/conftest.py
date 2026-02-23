import pytest
from fastapi.testclient import TestClient

from gitpulse.app import app


@pytest.fixture
def client():
	"""FastAPI test client."""
	return TestClient(app)
