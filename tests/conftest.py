"""Pytest configuration and shared fixtures for the test suite."""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from tests.fixtures.lens_api_responses import (
    get_mock_lens_api_response,
    get_empty_lens_api_response,
    get_single_result_response,
    get_boolean_search_response
)


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_lens_api_response():
    """Provide a standard mock Lens API response."""
    return get_mock_lens_api_response()


@pytest.fixture
def mock_empty_response():
    """Provide an empty mock Lens API response."""
    return get_empty_lens_api_response()


@pytest.fixture
def mock_single_result():
    """Provide a single result mock Lens API response."""
    return get_single_result_response()


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for testing HTTP calls."""
    with patch('requests.post') as mock_post:
        yield mock_post


@pytest.fixture
def mock_successful_api_call(mock_requests_post, mock_lens_api_response):
    """Configure mock for a successful API call."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_lens_api_response
    mock_response.raise_for_status.return_value = None
    mock_requests_post.return_value = mock_response
    return mock_requests_post


@pytest.fixture
def mock_api_error(mock_requests_post):
    """Configure mock for an API error."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "Bad Request"}
    mock_response.raise_for_status.side_effect = Exception("HTTP 400: Bad Request")
    mock_requests_post.return_value = mock_response
    return mock_requests_post


@pytest.fixture
def mock_api_timeout(mock_requests_post):
    """Configure mock for an API timeout."""
    import requests
    mock_requests_post.side_effect = requests.Timeout("Request timed out")
    return mock_requests_post


@pytest.fixture
def sample_user_input():
    """Provide a sample UserLensSearchInput for testing."""
    from app.schemas.lens_api_request import UserLensSearchInput
    return UserLensSearchInput(
        query_string='"machine learning" AND "healthcare"',
        fields=["title", "abstract"],
        default_operator="and",
        year_from=2020,
        year_to=2024,
        size=10,
        offset=0
    )


@pytest.fixture
def boolean_search_inputs():
    """Provide various boolean search inputs for testing."""
    from app.schemas.lens_api_request import UserLensSearchInput
    return {
        "simple_and": UserLensSearchInput(
            query_string='"machine learning" AND "healthcare"',
            fields=["title", "abstract"],
            size=10,
            offset=0
        ),
        "simple_or": UserLensSearchInput(
            query_string='"python" OR "javascript"',
            fields=["title", "abstract"],
            size=10,
            offset=0
        ),
        "complex_nested": UserLensSearchInput(
            query_string='("AI" OR "artificial intelligence") AND ("healthcare" OR "medical")',
            fields=["title", "abstract", "full_text"],
            size=10,
            offset=0
        ),
        "field_specific": UserLensSearchInput(
            query_string='title:"deep learning" AND abstract:"neural networks"',
            fields=["title", "abstract"],
            size=10,
            offset=0
        )
    }


@pytest.fixture
def pagination_test_cases():
    """Provide pagination test cases."""
    return [
        {"total": 100, "offset": 0, "size": 10, "expected_page": 1, "expected_total_pages": 10},
        {"total": 100, "offset": 50, "size": 10, "expected_page": 6, "expected_total_pages": 10},
        {"total": 95, "offset": 90, "size": 10, "expected_page": 10, "expected_total_pages": 10},
        {"total": 1, "offset": 0, "size": 10, "expected_page": 1, "expected_total_pages": 1},
        {"total": 0, "offset": 0, "size": 10, "expected_page": 1, "expected_total_pages": 1},
    ]


@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset application state between tests."""
    yield
    # Clean up any state that might persist between tests
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "boolean_search: mark test as boolean search related"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API related"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Custom pytest collection
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add markers based on test file names
        if "test_lens_client" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
            item.add_marker(pytest.mark.api)
        elif "test_boolean" in str(item.fspath):
            item.add_marker(pytest.mark.boolean_search)
        elif "test_search_endpoints" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.api)
        elif "test_schemas" in str(item.fspath):
            item.add_marker(pytest.mark.unit)