"""Unit tests for the LensAPIClient and related functionality."""

import pytest
from unittest.mock import Mock, patch
import requests
from pydantic import ValidationError

from app.services.lens_client import LensAPIClient, build_lens_request, build_example_request
from app.schemas.lens_api_request import UserLensSearchInput, LensSearchRequest
from app.schemas.search_response import LensAPIFullResponse
from tests.fixtures.lens_api_responses import (
    get_mock_lens_api_response,
    get_empty_lens_api_response,
    get_single_result_response,
    get_boolean_search_response
)


class TestLensAPIClient:
    """Test cases for the LensAPIClient class."""

    def test_client_initialization(self):
        """Test that LensAPIClient initializes correctly."""
        client = LensAPIClient()
        assert client._url.endswith("/search")
        assert client._token is not None

    @pytest.mark.unit
    def test_successful_search(self, mock_successful_api_call, sample_user_input):
        """Test successful API search call."""
        client = LensAPIClient()
        request_payload = build_lens_request(sample_user_input)
        
        result = client.search(request_payload)
        
        assert isinstance(result, LensAPIFullResponse)
        assert result.total == 81
        assert result.max_score == 18.112701
        assert len(result.data) == 2
        
        # Verify the API was called correctly
        mock_successful_api_call.assert_called_once()
        call_args = mock_successful_api_call.call_args
        assert call_args[1]['json'] == request_payload.dict(by_alias=True)
        assert call_args[1]['headers']['Content-Type'] == 'application/json'
        assert 'Authorization' in call_args[1]['headers']

    @pytest.mark.unit
    def test_empty_search_results(self, mock_requests_post, mock_empty_response):
        """Test handling of empty search results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_empty_response
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        client = LensAPIClient()
        request_payload = build_example_request()
        
        result = client.search(request_payload)
        
        assert isinstance(result, LensAPIFullResponse)
        assert result.total == 0
        assert result.max_score is None
        assert len(result.data) == 0

    @pytest.mark.unit
    def test_single_result(self, mock_requests_post, mock_single_result):
        """Test handling of single search result."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_single_result
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        client = LensAPIClient()
        request_payload = build_example_request()
        
        result = client.search(request_payload)
        
        assert isinstance(result, LensAPIFullResponse)
        assert result.total == 1
        assert result.max_score == 15.5
        assert len(result.data) == 1
        assert result.data[0]['lens_id'] == "001-123-456-789-000"

    @pytest.mark.unit
    def test_http_error_handling(self, mock_api_error):
        """Test handling of HTTP errors."""
        client = LensAPIClient()
        request_payload = build_example_request()
        
        with pytest.raises(Exception) as exc_info:
            client.search(request_payload)
        
        assert "HTTP 400: Bad Request" in str(exc_info.value)

    @pytest.mark.unit
    def test_timeout_handling(self, mock_api_timeout):
        """Test handling of request timeouts."""
        client = LensAPIClient()
        request_payload = build_example_request()
        
        with pytest.raises(requests.Timeout):
            client.search(request_payload)

    @pytest.mark.unit
    def test_network_error_handling(self, mock_requests_post):
        """Test handling of network errors."""
        mock_requests_post.side_effect = requests.ConnectionError("Network error")
        
        client = LensAPIClient()
        request_payload = build_example_request()
        
        with pytest.raises(requests.ConnectionError):
            client.search(request_payload)

    @pytest.mark.unit
    def test_malformed_response_handling(self, mock_requests_post):
        """Test handling of malformed API responses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}  # Missing required fields
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        client = LensAPIClient()
        request_payload = build_example_request()
        
        # Should handle missing fields gracefully by using defaults
        result = client.search(request_payload)
        assert result.total == 0  # Default value from missing field
        assert result.max_score is None
        assert result.data == []  # Default value from missing field


class TestBuildLensRequest:
    """Test cases for the build_lens_request function."""

    @pytest.mark.unit
    def test_basic_request_building(self):
        """Test building a basic lens request."""
        user_input = UserLensSearchInput(
            query_string='"machine learning"',
            fields=["title", "abstract"],
            size=10,
            offset=0
        )
        
        request = build_lens_request(user_input)
        
        assert isinstance(request, LensSearchRequest)
        assert request.size == 10
        assert request.from_ == 0
        assert "title" in request.include
        assert "abstract" in request.include
        assert "bool" in request.query

    @pytest.mark.unit
    @pytest.mark.boolean_search
    def test_boolean_query_construction(self):
        """Test construction of boolean queries."""
        user_input = UserLensSearchInput(
            query_string='"AI" AND "healthcare"',
            fields=["title", "abstract"],
            default_operator="and"
        )
        
        request = build_lens_request(user_input)
        
        # Verify the query structure contains boolean logic
        assert "bool" in request.query
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        assert len(bool_query.must) > 0

    @pytest.mark.unit
    def test_date_range_filtering(self):
        """Test date range filtering in requests."""
        user_input = UserLensSearchInput(
            query_string='"machine learning"',
            year_from=2020,
            year_to=2024,
            fields=["title"]
        )
        
        request = build_lens_request(user_input)
        
        # Verify date range is included in filter
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'filter')
        assert len(bool_query.filter) > 0

    @pytest.mark.unit
    def test_sorting_configuration(self):
        """Test sorting configuration in requests."""
        user_input = UserLensSearchInput(
            query_string='"test"',
            sort_by=[{"relevance": "desc"}, {"year_published": "desc"}]
        )
        
        request = build_lens_request(user_input)
        
        assert request.sort is not None
        assert len(request.sort) == 2

    @pytest.mark.unit
    def test_pagination_parameters(self):
        """Test pagination parameters in requests."""
        user_input = UserLensSearchInput(
            query_string='"test"',
            size=25,
            offset=50
        )
        
        request = build_lens_request(user_input)
        
        assert request.size == 25
        assert request.from_ == 50

    @pytest.mark.unit
    def test_field_selection(self):
        """Test field selection in requests."""
        user_input = UserLensSearchInput(
            query_string='"test"',
            include_fields=["title", "abstract", "authors", "year_published"]
        )
        
        request = build_lens_request(user_input)
        
        assert request.include == ["title", "abstract", "authors", "year_published"]


class TestBuildExampleRequest:
    """Test cases for the build_example_request function."""

    @pytest.mark.unit
    def test_example_request_structure(self):
        """Test that example request has correct structure."""
        request = build_example_request()
        
        assert isinstance(request, LensSearchRequest)
        assert request.size == 10
        assert request.from_ == 0
        assert request.include is not None
        assert "bool" in request.query

    @pytest.mark.unit
    def test_example_request_boolean_logic(self):
        """Test boolean logic in example request."""
        request = build_example_request()
        
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        assert hasattr(bool_query, 'filter')
        assert len(bool_query.must) > 0
        assert len(bool_query.filter) > 0

    @pytest.mark.unit
    def test_example_request_serialization(self):
        """Test that example request can be serialized properly."""
        request = build_example_request()
        
        # Should not raise any exceptions
        serialized = request.dict(by_alias=True)
        assert isinstance(serialized, dict)
        assert "query" in serialized
        assert "sort" in serialized
        assert "size" in serialized
        assert "from" in serialized  # Note: uses alias


class TestBooleanSearchQueries:
    """Test cases specifically for boolean search functionality."""

    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_type,expected_total", [
        ("simple_and", 45),
        ("simple_or", 156),
        ("complex_nested", 89),
        ("field_specific", 23)
    ])
    def test_boolean_search_types(self, mock_requests_post, query_type, expected_total):
        """Test different types of boolean searches."""
        mock_response = Mock()
        mock_response.status_code = 200
        # Get the response data from the boolean search responses
        boolean_response = get_boolean_search_response(query_type)
        mock_response.json.return_value = boolean_response
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        client = LensAPIClient()
        request_payload = build_example_request()
        
        result = client.search(request_payload)
        
        assert result.total == expected_total
        assert len(result.data) > 0

    @pytest.mark.boolean_search
    def test_and_operator_query(self, boolean_search_inputs):
        """Test AND operator in boolean queries."""
        user_input = boolean_search_inputs["simple_and"]
        request = build_lens_request(user_input)
        
        # Verify the query contains the expected structure
        assert "bool" in request.query
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')

    @pytest.mark.boolean_search
    def test_or_operator_query(self, boolean_search_inputs):
        """Test OR operator in boolean queries."""
        user_input = boolean_search_inputs["simple_or"]
        request = build_lens_request(user_input)
        
        # Verify the query structure
        assert "bool" in request.query
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')

    @pytest.mark.boolean_search
    def test_complex_nested_query(self, boolean_search_inputs):
        """Test complex nested boolean queries."""
        user_input = boolean_search_inputs["complex_nested"]
        request = build_lens_request(user_input)
        
        # Verify the query structure can handle complexity
        assert "bool" in request.query
        serialized = request.dict(by_alias=True)
        assert isinstance(serialized, dict)

    @pytest.mark.boolean_search
    def test_field_specific_query(self, boolean_search_inputs):
        """Test field-specific boolean queries."""
        user_input = boolean_search_inputs["field_specific"]
        request = build_lens_request(user_input)
        
        # Verify the query structure
        assert "bool" in request.query
        # Field-specific queries should still be properly structured
        serialized = request.dict(by_alias=True)
        assert "query" in serialized


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    @pytest.mark.unit
    def test_invalid_user_input(self):
        """Test handling of invalid user input."""
        # Test with invalid default_operator - this should raise ValidationError
        with pytest.raises(ValidationError):
            UserLensSearchInput(
                query_string="valid query",
                default_operator="invalid_operator"  # Should be "and" or "or"
            )

    @pytest.mark.unit
    def test_api_validation_error(self, mock_requests_post):
        """Test handling of API validation errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": "invalid",  # Should be int
            "max_score": "invalid",  # Should be float
            "data": "invalid"  # Should be list
        }
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        client = LensAPIClient()
        request_payload = build_example_request()
        
        with pytest.raises(ValidationError):
            client.search(request_payload)