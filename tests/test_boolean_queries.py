"""Comprehensive tests for boolean search functionality."""

import pytest
from typing import Dict, Any

from app.services.lens_client import build_lens_request
from app.schemas.lens_api_request import UserLensSearchInput, LensSearchRequest
from tests.fixtures.test_queries import (
    BASIC_BOOLEAN_QUERIES,
    COMPLEX_BOOLEAN_QUERIES,
    FIELD_SPECIFIC_QUERIES,
    EDGE_CASE_QUERIES,
    DATE_RANGE_BOOLEAN_QUERIES,
    create_user_search_input
)


class TestBasicBooleanOperators:
    """Test basic boolean operators (AND, OR, NOT)."""

    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", BASIC_BOOLEAN_QUERIES)
    def test_basic_boolean_queries(self, query_data):
        """Test basic boolean query construction."""
        user_input = create_user_search_input(query_data["query"])
        request = build_lens_request(user_input)
        
        assert isinstance(request, LensSearchRequest)
        assert "bool" in request.query
        
        # Verify the request can be serialized (no structural issues)
        serialized = request.dict(by_alias=True)
        assert "query" in serialized
        assert "bool" in serialized["query"]

    @pytest.mark.boolean_search
    def test_simple_and_operator(self):
        """Test simple AND operator functionality."""
        query = '"machine learning" AND "healthcare"'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        assert len(bool_query.must) > 0
        
        # Verify query string is properly constructed
        query_string_query = bool_query.must[0]
        assert hasattr(query_string_query, 'query_string')
        assert query_string_query.query_string["query"] == query

    @pytest.mark.boolean_search
    def test_simple_or_operator(self):
        """Test simple OR operator functionality."""
        query = '"python" OR "javascript"'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        
        # Verify the OR logic is captured in the query string
        query_string_query = bool_query.must[0]
        assert query_string_query.query_string["query"] == query

    @pytest.mark.boolean_search
    def test_not_operator(self):
        """Test NOT operator functionality."""
        query = '"artificial intelligence" NOT "robotics"'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Should still construct a valid query
        assert "bool" in request.query
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')

    @pytest.mark.boolean_search
    def test_case_insensitive_operators(self):
        """Test that boolean operators work regardless of case."""
        queries = [
            '"term1" AND "term2"',
            '"term1" and "term2"',
            '"term1" And "term2"'
        ]
        
        for query in queries:
            user_input = create_user_search_input(query)
            request = build_lens_request(user_input)
            
            # All should produce valid requests
            assert "bool" in request.query
            serialized = request.dict(by_alias=True)
            assert isinstance(serialized, dict)


class TestComplexBooleanLogic:
    """Test complex boolean logic with nested operations."""

    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", COMPLEX_BOOLEAN_QUERIES)
    def test_complex_boolean_queries(self, query_data):
        """Test complex boolean query construction."""
        user_input = create_user_search_input(query_data["query"])
        request = build_lens_request(user_input)
        
        assert isinstance(request, LensSearchRequest)
        assert "bool" in request.query
        
        # Complex queries should still serialize properly
        serialized = request.dict(by_alias=True)
        assert "query" in serialized

    @pytest.mark.boolean_search
    def test_nested_parentheses(self):
        """Test nested parentheses in boolean queries."""
        query = '("AI" OR "artificial intelligence") AND ("healthcare" OR "medical")'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Should handle nested logic without errors
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        
        # Verify the complex query is preserved
        query_string_query = bool_query.must[0]
        assert query_string_query.query_string["query"] == query

    @pytest.mark.boolean_search
    def test_multiple_levels_nesting(self):
        """Test multiple levels of nesting in boolean queries."""
        query = '(("machine learning" OR "ML") AND "healthcare") OR (("artificial intelligence" OR "AI") AND "medical")'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Should construct without errors
        assert "bool" in request.query
        serialized = request.dict(by_alias=True)
        assert isinstance(serialized, dict)

    @pytest.mark.boolean_search
    def test_mixed_operators_with_parentheses(self):
        """Test mixed AND/OR operators with parentheses."""
        query = '"deep learning" AND ("computer vision" OR "natural language processing" OR "speech recognition")'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        
        # Verify complex query structure is maintained
        query_string_query = bool_query.must[0]
        assert query_string_query.query_string["query"] == query


class TestFieldSpecificBooleanQueries:
    """Test boolean queries with field-specific searches."""

    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", FIELD_SPECIFIC_QUERIES)
    def test_field_specific_queries(self, query_data):
        """Test field-specific boolean queries."""
        user_input = create_user_search_input(query_data["query"])
        request = build_lens_request(user_input)
        
        assert isinstance(request, LensSearchRequest)
        assert "bool" in request.query
        
        # Field-specific queries should serialize properly
        serialized = request.dict(by_alias=True)
        assert "query" in serialized

    @pytest.mark.boolean_search
    def test_title_and_abstract_fields(self):
        """Test boolean search across title and abstract fields."""
        query = 'title:"deep learning" AND abstract:"neural networks"'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')
        
        # Verify field-specific query is preserved
        query_string_query = bool_query.must[0]
        assert query_string_query.query_string["query"] == query

    @pytest.mark.boolean_search
    def test_multiple_field_boolean_search(self):
        """Test boolean search across multiple specific fields."""
        query = 'title:("AI" OR "artificial intelligence") AND abstract:"healthcare" AND full_text:"machine learning"'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Should handle multiple field specifications
        assert "bool" in request.query
        bool_query = request.query["bool"]
        assert hasattr(bool_query, 'must')

    @pytest.mark.boolean_search
    def test_field_with_complex_boolean_logic(self):
        """Test field-specific searches with complex boolean logic."""
        query = 'title:(("deep learning" OR "neural networks") AND "applications") OR abstract:("computer vision" AND "medical imaging")'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Complex field-specific queries should work
        assert "bool" in request.query
        serialized = request.dict(by_alias=True)
        assert isinstance(serialized, dict)


class TestBooleanQueryWithFilters:
    """Test boolean queries combined with other filters."""

    @pytest.mark.boolean_search
    @pytest.mark.parametrize("query_data", DATE_RANGE_BOOLEAN_QUERIES)
    def test_boolean_with_date_range(self, query_data):
        """Test boolean queries with date range filters."""
        user_input = create_user_search_input(
            query_data["query"],
            year_from=query_data.get("year_from"),
            year_to=query_data.get("year_to")
        )
        request = build_lens_request(user_input)
        
        assert "bool" in request.query
        bool_query = request.query["bool"]
        
        # Should have both query and filter components
        assert hasattr(bool_query, 'must')
        if query_data.get("year_from") or query_data.get("year_to"):
            assert hasattr(bool_query, 'filter')
            assert len(bool_query.filter) > 0

    @pytest.mark.boolean_search
    def test_boolean_with_field_restrictions(self):
        """Test boolean queries with field restrictions."""
        query = '"machine learning" AND "healthcare"'
        user_input = create_user_search_input(
            query,
            fields=["title", "abstract"]
        )
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        query_string_query = bool_query.must[0]
        
        # Verify fields are properly set
        assert "fields" in query_string_query.query_string
        assert query_string_query.query_string["fields"] == ["title", "abstract"]

    @pytest.mark.boolean_search
    def test_boolean_with_default_operator(self):
        """Test boolean queries with different default operators."""
        query = '"machine learning" "healthcare"'  # No explicit operator
        
        for operator in ["and", "or"]:
            user_input = create_user_search_input(
                query,
                default_operator=operator
            )
            request = build_lens_request(user_input)
            
            bool_query = request.query["bool"]
            query_string_query = bool_query.must[0]
            
            # Verify default operator is set
            assert query_string_query.query_string["default_operator"] == operator


class TestBooleanQueryEdgeCases:
    """Test edge cases and error conditions for boolean queries."""

    @pytest.mark.boolean_search
    def test_empty_query_handling(self):
        """Test handling of empty queries."""
        # Empty query string should be allowed by UserLensSearchInput
        # The validation happens at the API level, not the schema level
        user_input = create_user_search_input("")
        assert user_input.query_string == ""

    @pytest.mark.boolean_search
    def test_only_operators_query(self):
        """Test query with only boolean operators."""
        query = "AND OR NOT"
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Should still construct a request (API will handle the invalid query)
        assert "bool" in request.query

    @pytest.mark.boolean_search
    def test_unmatched_parentheses(self):
        """Test queries with unmatched parentheses."""
        queries = [
            '("machine learning" AND "AI"',  # Missing closing
            '"machine learning" AND "AI")',  # Missing opening
            '(("nested" AND "query")',       # Unbalanced nesting
        ]
        
        for query in queries:
            user_input = create_user_search_input(query)
            request = build_lens_request(user_input)
            
            # Should still construct (API will validate syntax)
            assert "bool" in request.query

    @pytest.mark.boolean_search
    def test_special_characters_in_boolean_query(self):
        """Test boolean queries with special characters."""
        query = '"machine-learning" AND "AI/ML" AND "C++"'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        query_string_query = bool_query.must[0]
        
        # Special characters should be preserved
        assert query_string_query.query_string["query"] == query

    @pytest.mark.boolean_search
    def test_very_long_boolean_query(self):
        """Test very long boolean queries."""
        # Create a long query with many terms
        terms = [f'"term{i}"' for i in range(50)]
        query = " AND ".join(terms)
        
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        # Should handle long queries
        assert "bool" in request.query
        bool_query = request.query["bool"]
        query_string_query = bool_query.must[0]
        # The actual query length will be less than expected due to formatting
        assert len(query_string_query.query_string["query"]) > 500

    @pytest.mark.boolean_search
    def test_unicode_in_boolean_query(self):
        """Test boolean queries with unicode characters."""
        query = '"机器学习" AND "人工智能"'  # Chinese characters
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        bool_query = request.query["bool"]
        query_string_query = bool_query.must[0]
        
        # Unicode should be preserved
        assert query_string_query.query_string["query"] == query


class TestBooleanQueryPerformance:
    """Test performance aspects of boolean query construction."""

    @pytest.mark.boolean_search
    @pytest.mark.slow
    def test_complex_query_construction_performance(self):
        """Test that complex query construction is reasonably fast."""
        import time
        
        # Create a very complex query
        query = '(("AI" OR "artificial intelligence" OR "machine learning" OR "ML") AND ("healthcare" OR "medical" OR "clinical" OR "hospital")) OR (("computer vision" OR "image processing") AND ("diagnosis" OR "detection" OR "analysis"))'
        
        start_time = time.time()
        for _ in range(100):  # Build the same query 100 times
            user_input = create_user_search_input(query)
            request = build_lens_request(user_input)
            assert "bool" in request.query
        
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second for 100 iterations)
        assert (end_time - start_time) < 1.0

    @pytest.mark.boolean_search
    def test_query_serialization_performance(self):
        """Test that query serialization is reasonably fast."""
        import time
        
        query = '("deep learning" OR "neural networks") AND ("computer vision" OR "NLP")'
        user_input = create_user_search_input(query)
        request = build_lens_request(user_input)
        
        start_time = time.time()
        for _ in range(1000):  # Serialize 1000 times
            serialized = request.dict(by_alias=True)
            assert isinstance(serialized, dict)
        
        end_time = time.time()
        
        # Should complete quickly (less than 0.5 seconds for 1000 iterations)
        assert (end_time - start_time) < 0.5