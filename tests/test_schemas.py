"""Tests for schema validation and response structures."""

import pytest
from pydantic import ValidationError
from typing import Dict, Any

from app.schemas.search_response import (
    PaginationMetadata,
    EnrichedSearchResponse,
    LensAPIFullResponse
)
from app.schemas.lens_api_request import (
    UserLensSearchInput,
    LensSearchRequest,
    BoolQuery,
    QueryStringQuery,
    RangeQuery,
    SortField
)
from app.schemas.lens_api_response import ScholarResponse
from tests.fixtures.test_queries import PAGINATION_TEST_CASES


class TestPaginationMetadata:
    """Test cases for PaginationMetadata schema."""

    @pytest.mark.unit
    @pytest.mark.parametrize("test_case", PAGINATION_TEST_CASES)
    def test_pagination_calculation(self, test_case):
        """Test pagination metadata calculation with various scenarios."""
        pagination = PaginationMetadata.create(
            total=test_case["total"],
            offset=test_case["offset"],
            size=test_case["size"]
        )
        
        assert pagination.total == test_case["total"]
        assert pagination.page == test_case["expected_page"]
        assert pagination.size == test_case["size"]
        assert pagination.total_pages == test_case["expected_total_pages"]

    @pytest.mark.unit
    def test_pagination_edge_cases(self):
        """Test pagination edge cases."""
        # Zero size should default to 1 page
        pagination = PaginationMetadata.create(total=100, offset=0, size=0)
        assert pagination.page == 1
        assert pagination.total_pages == 1
        
        # Large offset beyond total
        pagination = PaginationMetadata.create(total=10, offset=100, size=10)
        assert pagination.page == 11  # (100 // 10) + 1
        assert pagination.total_pages == 1  # ceil(10 / 10)

    @pytest.mark.unit
    def test_pagination_validation(self):
        """Test pagination metadata validation."""
        # Valid pagination
        pagination = PaginationMetadata(
            total=100,
            page=5,
            size=10,
            total_pages=10
        )
        assert pagination.total == 100
        
        # Test that negative values are handled (Pydantic may not enforce this by default)
        # Just test that we can create pagination with edge cases
        pagination_edge = PaginationMetadata(
            total=0,
            page=1,
            size=10,
            total_pages=1
        )
        assert pagination_edge.total == 0

    @pytest.mark.unit
    def test_pagination_serialization(self):
        """Test pagination metadata serialization."""
        pagination = PaginationMetadata.create(total=81, offset=20, size=10)
        
        serialized = pagination.dict()
        assert serialized == {
            "total": 81,
            "page": 3,
            "size": 10,
            "total_pages": 9
        }


class TestEnrichedSearchResponse:
    """Test cases for EnrichedSearchResponse schema."""

    @pytest.mark.unit
    def test_enriched_response_creation(self):
        """Test creation of enriched search response."""
        # Create mock data
        mock_article = ScholarResponse(
            lens_id="test-123",
            title="Test Article",
            year_published=2023
        )
        
        pagination = PaginationMetadata.create(total=1, offset=0, size=10)
        
        response = EnrichedSearchResponse(
            data=[mock_article],
            pagination=pagination,
            max_score=18.5
        )
        
        assert len(response.data) == 1
        assert response.data[0].lens_id == "test-123"
        assert response.pagination.total == 1
        assert response.max_score == 18.5

    @pytest.mark.unit
    def test_enriched_response_empty_data(self):
        """Test enriched response with empty data."""
        pagination = PaginationMetadata.create(total=0, offset=0, size=10)
        
        response = EnrichedSearchResponse(
            data=[],
            pagination=pagination,
            max_score=None
        )
        
        assert len(response.data) == 0
        assert response.pagination.total == 0
        assert response.max_score is None

    @pytest.mark.unit
    def test_enriched_response_validation(self):
        """Test enriched response validation."""
        pagination = PaginationMetadata.create(total=1, offset=0, size=10)
        
        # Valid response
        response = EnrichedSearchResponse(
            data=[],
            pagination=pagination,
            max_score=15.5
        )
        assert isinstance(response, EnrichedSearchResponse)
        
        # Invalid data type should raise ValidationError
        with pytest.raises(ValidationError):
            EnrichedSearchResponse(
                data="invalid",  # Should be list
                pagination=pagination,
                max_score=15.5
            )

    @pytest.mark.unit
    def test_enriched_response_serialization(self):
        """Test enriched response serialization."""
        mock_article = ScholarResponse(
            lens_id="test-123",
            title="Test Article"
        )
        
        pagination = PaginationMetadata.create(total=1, offset=0, size=10)
        
        response = EnrichedSearchResponse(
            data=[mock_article],
            pagination=pagination,
            max_score=18.5
        )
        
        serialized = response.dict()
        assert "data" in serialized
        assert "pagination" in serialized
        assert "max_score" in serialized
        assert serialized["max_score"] == 18.5


class TestLensAPIFullResponse:
    """Test cases for LensAPIFullResponse schema."""

    @pytest.mark.unit
    def test_lens_api_response_creation(self):
        """Test creation of Lens API full response."""
        response = LensAPIFullResponse(
            total=81,
            max_score=18.112701,
            data=[
                {"lens_id": "test-123", "title": "Test Article"},
                {"lens_id": "test-456", "title": "Another Article"}
            ]
        )
        
        assert response.total == 81
        assert response.max_score == 18.112701
        assert len(response.data) == 2

    @pytest.mark.unit
    def test_lens_api_response_optional_fields(self):
        """Test Lens API response with optional fields."""
        # max_score can be None
        response = LensAPIFullResponse(
            total=0,
            max_score=None,
            data=[]
        )
        
        assert response.total == 0
        assert response.max_score is None
        assert len(response.data) == 0

    @pytest.mark.unit
    def test_lens_api_response_validation(self):
        """Test Lens API response validation."""
        # Valid response
        response = LensAPIFullResponse(
            total=10,
            max_score=15.5,
            data=[{"lens_id": "test"}]
        )
        assert response.total == 10
        
        # Invalid total type
        with pytest.raises(ValidationError):
            LensAPIFullResponse(
                total="invalid",  # Should be int
                max_score=15.5,
                data=[]
            )


class TestUserLensSearchInput:
    """Test cases for UserLensSearchInput schema."""

    @pytest.mark.unit
    def test_user_search_input_creation(self):
        """Test creation of user search input."""
        user_input = UserLensSearchInput(
            query_string='"machine learning"',
            fields=["title", "abstract"],
            default_operator="and",
            year_from=2020,
            year_to=2024,
            size=10,
            offset=0
        )
        
        assert user_input.query_string == '"machine learning"'
        assert user_input.fields == ["title", "abstract"]
        assert user_input.default_operator == "and"
        assert user_input.year_from == 2020
        assert user_input.year_to == 2024

    @pytest.mark.unit
    def test_user_search_input_defaults(self):
        """Test default values for user search input."""
        user_input = UserLensSearchInput(
            query_string='"test query"'
        )
        
        # Check default values
        assert user_input.fields == ["title", "abstract", "full_text"]
        assert user_input.default_operator == "and"
        assert user_input.year_from is None
        assert user_input.year_to is None
        assert user_input.size == 10
        assert user_input.offset == 0

    @pytest.mark.unit
    def test_user_search_input_validation(self):
        """Test user search input validation."""
        # Valid input
        user_input = UserLensSearchInput(
            query_string='"valid query"',
            size=25,
            offset=50
        )
        assert user_input.size == 25
        assert user_input.offset == 50
        
        # Invalid operator
        with pytest.raises(ValidationError):
            UserLensSearchInput(
                query_string='"test"',
                default_operator="invalid"  # Should be "and" or "or"
            )

    @pytest.mark.unit
    def test_user_search_input_boolean_queries(self):
        """Test user search input with boolean queries."""
        boolean_queries = [
            '"term1" AND "term2"',
            '"term1" OR "term2"',
            '("AI" OR "ML") AND "healthcare"',
            'title:"deep learning" AND abstract:"neural networks"'
        ]
        
        for query in boolean_queries:
            user_input = UserLensSearchInput(query_string=query)
            assert user_input.query_string == query


class TestLensSearchRequest:
    """Test cases for LensSearchRequest schema."""

    @pytest.mark.unit
    def test_lens_search_request_creation(self):
        """Test creation of lens search request."""
        query_string = QueryStringQuery(
            query_string={
                "query": '"test query"',
                "fields": ["title"],
                "default_operator": "and"
            }
        )
        
        bool_query = BoolQuery(must=[query_string])
        
        request = LensSearchRequest(
            query={"bool": bool_query},
            size=10,
            from_=0,
            include=["title", "abstract"]
        )
        
        assert request.size == 10
        assert request.from_ == 0
        assert request.include == ["title", "abstract"]

    @pytest.mark.unit
    def test_lens_search_request_serialization(self):
        """Test lens search request serialization with aliases."""
        query_string = QueryStringQuery(
            query_string={
                "query": '"test"',
                "fields": ["title"]
            }
        )
        
        bool_query = BoolQuery(must=[query_string])
        
        request = LensSearchRequest(
            query={"bool": bool_query},
            size=20,
            from_=10
        )
        
        # Test serialization with aliases
        serialized = request.dict(by_alias=True)
        assert "from" in serialized  # Should use alias, not from_
        assert serialized["from"] == 10
        assert serialized["size"] == 20

    @pytest.mark.unit
    def test_lens_search_request_with_filters(self):
        """Test lens search request with date range filters."""
        query_string = QueryStringQuery(
            query_string={"query": '"test"'}
        )
        
        range_query = RangeQuery(
            range={
                "year_published": {
                    "gte": 2020,
                    "lte": 2024
                }
            }
        )
        
        bool_query = BoolQuery(
            must=[query_string],
            filter=[range_query]
        )
        
        request = LensSearchRequest(
            query={"bool": bool_query},
            size=10
        )
        
        # Should serialize without errors
        serialized = request.dict(by_alias=True)
        assert "query" in serialized
        assert "bool" in serialized["query"]


class TestScholarResponse:
    """Test cases for ScholarResponse schema."""

    @pytest.mark.unit
    def test_scholar_response_creation(self):
        """Test creation of scholar response."""
        response = ScholarResponse(
            lens_id="test-123-456",
            title="Test Article Title",
            year_published=2023,
            publication_type="journal article"
        )
        
        assert response.lens_id == "test-123-456"
        assert response.title == "Test Article Title"
        assert response.year_published == 2023

    @pytest.mark.unit
    def test_scholar_response_optional_fields(self):
        """Test scholar response with optional fields."""
        # Only required field is lens_id
        response = ScholarResponse(lens_id="minimal-test")
        
        assert response.lens_id == "minimal-test"
        assert response.title is None
        assert response.abstract is None
        assert response.year_published is None

    @pytest.mark.unit
    def test_scholar_response_with_complex_data(self):
        """Test scholar response with complex nested data."""
        # Use raw dict data as it would come from the API
        response = ScholarResponse(
            lens_id="complex-test",
            title="Complex Article",
            authors=[
                {
                    "collective_name": None,
                    "first_name": "John",
                    "last_name": "Doe",
                    "initials": "J.D.",
                    "affiliations": [
                        {
                            "name": "University",
                            "name_original": None,
                            "grid_id": None,
                            "country_code": "US",
                            "ids": None
                        }
                    ],
                    "ids": None
                }
            ],
            source={
                "title": "Journal Name",
                "type": "journal",
                "publisher": "Publisher",
                "issn": None,
                "country": None,
                "asjc_codes": None,
                "asjc_subjects": None
            }
        )
        
        assert response.lens_id == "complex-test"
        assert len(response.authors) == 1
        assert response.authors[0].first_name == "John"
        assert response.source.title == "Journal Name"


class TestSortField:
    """Test cases for SortField schema."""

    @pytest.mark.unit
    def test_sort_field_creation(self):
        """Test creation of sort fields."""
        sort_field = SortField({"relevance": "desc"})
        assert sort_field.root == {"relevance": "desc"}
        
        sort_field = SortField({"year_published": "asc"})
        assert sort_field.root == {"year_published": "asc"}

    @pytest.mark.unit
    def test_sort_field_validation(self):
        """Test sort field validation."""
        # Valid sort directions
        valid_sorts = [
            {"relevance": "desc"},
            {"year_published": "asc"},
            {"title": "desc"}
        ]
        
        for sort_dict in valid_sorts:
            sort_field = SortField(sort_dict)
            assert isinstance(sort_field, SortField)
        
        # Invalid sort direction should raise ValidationError
        with pytest.raises(ValidationError):
            SortField({"relevance": "invalid"})


class TestQueryComponents:
    """Test cases for query component schemas."""

    @pytest.mark.unit
    def test_query_string_query(self):
        """Test QueryStringQuery schema."""
        query = QueryStringQuery(
            query_string={
                "query": '"machine learning" AND "AI"',
                "fields": ["title", "abstract"],
                "default_operator": "and"
            }
        )
        
        assert query.query_string["query"] == '"machine learning" AND "AI"'
        assert query.query_string["fields"] == ["title", "abstract"]

    @pytest.mark.unit
    def test_range_query(self):
        """Test RangeQuery schema."""
        range_query = RangeQuery(
            range={
                "year_published": {
                    "gte": 2020,
                    "lte": 2024
                }
            }
        )
        
        assert range_query.range["year_published"]["gte"] == 2020
        assert range_query.range["year_published"]["lte"] == 2024

    @pytest.mark.unit
    def test_bool_query(self):
        """Test BoolQuery schema."""
        query_string = QueryStringQuery(
            query_string={"query": '"test"'}
        )
        
        range_query = RangeQuery(
            range={"year_published": {"gte": 2020}}
        )
        
        bool_query = BoolQuery(
            must=[query_string],
            filter=[range_query]
        )
        
        assert len(bool_query.must) == 1
        assert len(bool_query.filter) == 1
        assert bool_query.should is None
        assert bool_query.must_not is None


class TestSchemaIntegration:
    """Test integration between different schemas."""

    @pytest.mark.unit
    def test_full_request_response_cycle(self):
        """Test complete request-response schema cycle."""
        # Create user input
        user_input = UserLensSearchInput(
            query_string='"machine learning" AND "healthcare"',
            fields=["title", "abstract"],
            year_from=2020,
            size=10,
            offset=0
        )
        
        # This would normally go through build_lens_request
        # but we'll test the schemas directly
        
        # Mock API response
        api_response = LensAPIFullResponse(
            total=45,
            max_score=19.2,
            data=[
                {
                    "lens_id": "test-123",
                    "title": "ML in Healthcare",
                    "year_published": 2023
                }
            ]
        )
        
        # Create enriched response
        scholar_articles = [ScholarResponse(**item) for item in api_response.data]
        pagination = PaginationMetadata.create(
            total=api_response.total,
            offset=user_input.offset,
            size=user_input.size
        )
        
        enriched_response = EnrichedSearchResponse(
            data=scholar_articles,
            pagination=pagination,
            max_score=api_response.max_score
        )
        
        # Verify the complete cycle
        assert len(enriched_response.data) == 1
        assert enriched_response.data[0].lens_id == "test-123"
        assert enriched_response.pagination.total == 45
        assert enriched_response.pagination.page == 1
        assert enriched_response.max_score == 19.2