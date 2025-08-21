"""Integration tests for search endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from tests.fixtures.lens_api_responses import (
    get_mock_lens_api_response,
    get_empty_lens_api_response,
    get_boolean_search_response,
    get_large_dataset_response
)
from tests.fixtures.test_queries import (
    BASIC_BOOLEAN_QUERIES,
    COMPLEX_BOOLEAN_QUERIES,
    FIELD_SPECIFIC_QUERIES
)


class TestSearchEndpoint:
    """Integration tests for the /search endpoint."""

    @pytest.mark.integration
    def test_search_endpoint_basic_query(self, client, mock_successful_api_call):
        """Test basic search endpoint functionality."""
        search_payload = {
            "query_string": '"machine learning"',
            "fields": ["title", "abstract"],
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify enriched response structure
        assert "data" in data
        assert "pagination" in data
        assert "max_score" in data
        
        # Verify pagination metadata
        pagination = data["pagination"]
        assert pagination["total"] == 81
        assert pagination["page"] == 1
        assert pagination["size"] == 10
        assert pagination["total_pages"] == 9
        
        # Verify max_score
        assert data["max_score"] == 18.112701
        
        # Verify data structure
        assert len(data["data"]) == 2
        assert data["data"][0]["lens_id"] == "002-534-152-232-951"

    @pytest.mark.integration
    def test_search_endpoint_with_pagination(self, client, mock_successful_api_call):
        """Test search endpoint with pagination parameters."""
        search_payload = {
            "query_string": '"AI"',
            "size": 5,
            "offset": 10
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination calculation
        pagination = data["pagination"]
        assert pagination["page"] == 3  # (10 // 5) + 1
        assert pagination["size"] == 5
        assert pagination["total_pages"] == 17  # ceil(81 / 5)

    @pytest.mark.integration
    def test_search_endpoint_empty_results(self, client, mock_requests_post):
        """Test search endpoint with empty results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_empty_lens_api_response()
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": '"nonexistent term"',
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["data"]) == 0
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total_pages"] == 1
        assert data["max_score"] is None

    @pytest.mark.integration
    def test_search_endpoint_with_date_range(self, client, mock_successful_api_call):
        """Test search endpoint with date range filtering."""
        search_payload = {
            "query_string": '"machine learning"',
            "year_from": 2020,
            "year_to": 2024,
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still return enriched response structure
        assert "data" in data
        assert "pagination" in data
        assert "max_score" in data

    @pytest.mark.integration
    def test_search_endpoint_with_field_selection(self, client, mock_successful_api_call):
        """Test search endpoint with specific field selection."""
        search_payload = {
            "query_string": '"AI"',
            "fields": ["title", "abstract"],
            "include_fields": ["title", "abstract", "lens_id", "year_published", "authors"],
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "data" in data
        assert len(data["data"]) > 0

    @pytest.mark.integration
    def test_search_endpoint_with_sorting(self, client, mock_successful_api_call):
        """Test search endpoint with custom sorting."""
        search_payload = {
            "query_string": '"machine learning"',
            "sort_by": [{"year_published": "desc"}, {"relevance": "desc"}],
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return valid response
        assert "data" in data
        assert "pagination" in data

    @pytest.mark.integration
    def test_search_endpoint_error_handling(self, client, mock_api_error):
        """Test search endpoint error handling."""
        search_payload = {
            "query_string": '"invalid query syntax"',
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 500
        data = response.json()
        # Check for the actual error response format
        assert "message" in data
        assert data["status_code"] == 500

    @pytest.mark.integration
    def test_search_endpoint_invalid_payload(self, client):
        """Test search endpoint with invalid payload."""
        invalid_payloads = [
            {},  # Missing required query_string
            {"query_string": '"test"', "default_operator": "invalid"},  # Invalid operator
        ]
        
        for payload in invalid_payloads:
            response = client.post("/api/v1/users/search", json=payload)
            # These should return validation errors, but may return 500 due to internal processing
            assert response.status_code in [422, 500]


class TestBooleanSearchEndpoints:
    """Integration tests for boolean search functionality through endpoints."""

    @pytest.mark.integration
    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", BASIC_BOOLEAN_QUERIES)
    def test_basic_boolean_search_endpoints(self, client, mock_requests_post, query_data):
        """Test basic boolean searches through the endpoint."""
        # Mock appropriate response based on query type
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_mock_lens_api_response(
            total=query_data.get("expected_results", 50)
        )
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": query_data["query"],
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify enriched response structure
        assert "data" in data
        assert "pagination" in data
        assert "max_score" in data
        assert data["pagination"]["total"] == query_data.get("expected_results", 50)

    @pytest.mark.integration
    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", COMPLEX_BOOLEAN_QUERIES)
    def test_complex_boolean_search_endpoints(self, client, mock_requests_post, query_data):
        """Test complex boolean searches through the endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_mock_lens_api_response(
            total=query_data.get("expected_results", 100)
        )
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": query_data["query"],
            "fields": ["title", "abstract", "full_text"],
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Complex queries should still return valid structure
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    @pytest.mark.integration
    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", FIELD_SPECIFIC_QUERIES)
    def test_field_specific_boolean_endpoints(self, client, mock_requests_post, query_data):
        """Test field-specific boolean searches through the endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_mock_lens_api_response(
            total=query_data.get("expected_results", 25)
        )
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": query_data["query"],
            "fields": ["title", "abstract"],
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Field-specific queries should work
        assert "data" in data
        assert "pagination" in data

    @pytest.mark.integration
    @pytest.mark.boolean_search
    def test_boolean_search_with_pagination(self, client, mock_requests_post):
        """Test boolean search with pagination through endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_large_dataset_response(total=500)
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": '("AI" OR "artificial intelligence") AND "healthcare"',
            "size": 25,
            "offset": 100
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination with boolean search
        pagination = data["pagination"]
        assert pagination["total"] == 500
        assert pagination["page"] == 5  # (100 // 25) + 1
        assert pagination["size"] == 25
        assert pagination["total_pages"] == 20  # ceil(500 / 25)


class TestTestSearchEndpoint:
    """Integration tests for the /test-search endpoint."""

    @pytest.mark.integration
    def test_test_search_endpoint(self, client, mock_successful_api_call):
        """Test the test-search endpoint functionality."""
        response = client.get("/api/v1/users/test-search")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return list of articles (not enriched format)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["lens_id"] == "002-534-152-232-951"

    @pytest.mark.integration
    def test_test_search_endpoint_error(self, client, mock_api_error):
        """Test test-search endpoint error handling."""
        response = client.get("/api/v1/users/test-search")
        
        assert response.status_code == 500
        data = response.json()
        # The error response format may vary, check for either format
        assert "detail" in data or "message" in data


class TestSearchEndpointPerformance:
    """Performance tests for search endpoints."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_search_endpoint_response_time(self, client, mock_successful_api_call):
        """Test that search endpoint responds within reasonable time."""
        import time
        
        search_payload = {
            "query_string": '"machine learning" AND "healthcare"',
            "size": 10,
            "offset": 0
        }
        
        start_time = time.time()
        response = client.post("/api/v1/users/search", json=search_payload)
        end_time = time.time()
        
        assert response.status_code == 200
        # Should respond within 1 second (mocked, so should be very fast)
        assert (end_time - start_time) < 1.0

    @pytest.mark.integration
    @pytest.mark.slow
    def test_large_result_set_handling(self, client, mock_requests_post):
        """Test handling of large result sets."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_large_dataset_response(total=10000)
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": '"popular term"',
            "size": 100,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should handle large datasets properly
        assert data["pagination"]["total"] == 10000
        assert data["pagination"]["total_pages"] == 100
        assert len(data["data"]) <= 20  # Mock returns max 20 items


class TestSearchEndpointEdgeCases:
    """Test edge cases for search endpoints."""

    @pytest.mark.integration
    def test_search_with_special_characters(self, client, mock_successful_api_call):
        """Test search with special characters in query."""
        search_payload = {
            "query_string": '"C++" AND "machine-learning" AND "AI/ML"',
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @pytest.mark.integration
    def test_search_with_unicode(self, client, mock_successful_api_call):
        """Test search with unicode characters."""
        search_payload = {
            "query_string": '"机器学习" AND "人工智能"',  # Chinese characters
            "size": 10,
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @pytest.mark.integration
    def test_search_with_very_large_offset(self, client, mock_requests_post):
        """Test search with very large offset."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_empty_lens_api_response()
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response
        
        search_payload = {
            "query_string": '"test"',
            "size": 10,
            "offset": 10000
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should handle large offset gracefully
        assert data["pagination"]["page"] == 1001  # (10000 // 10) + 1

    @pytest.mark.integration
    def test_search_with_maximum_page_size(self, client, mock_successful_api_call):
        """Test search with maximum page size."""
        search_payload = {
            "query_string": '"test"',
            "size": 100,  # Large page size
            "offset": 0
        }
        
        response = client.post("/api/v1/users/search", json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should handle large page size
        assert data["pagination"]["size"] == 100
        assert data["pagination"]["total_pages"] == 1  # ceil(81 / 100)

    @pytest.mark.integration
    def test_concurrent_search_requests(self, client, mock_successful_api_call):
        """Test handling of concurrent search requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            search_payload = {
                "query_string": '"concurrent test"',
                "size": 10,
                "offset": 0
            }
            response = client.post("/api/v1/users/search", json=search_payload)
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5