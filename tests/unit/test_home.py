import pytest
from app import app

def test_home_route():
    """Simple test to check the home route returns 200."""
    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200
