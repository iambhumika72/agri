from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verify health endpoint returns 200 and correct status."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "copernicus_hub" in data["dependencies"]

def test_docs_accessible():
    """Verify Swagger UI is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200

# Note: Integration testing for /forecast/ would require mocking
# SentinelAPI and GEE which is covered in unit tests.
