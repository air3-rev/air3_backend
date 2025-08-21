"""Test query examples for boolean search testing."""

from typing import Dict, Any, List
from app.schemas.lens_api_request import UserLensSearchInput


# Basic boolean search queries
BASIC_BOOLEAN_QUERIES = [
    {
        "name": "simple_and",
        "query": '"machine learning" AND "healthcare"',
        "description": "Simple AND operation between two terms",
        "expected_results": 45
    },
    {
        "name": "simple_or", 
        "query": '"python" OR "javascript"',
        "description": "Simple OR operation between two terms",
        "expected_results": 156
    },
    {
        "name": "simple_not",
        "query": '"artificial intelligence" NOT "robotics"',
        "description": "Simple NOT operation to exclude terms",
        "expected_results": 78
    }
]

# Complex boolean search queries
COMPLEX_BOOLEAN_QUERIES = [
    {
        "name": "nested_parentheses",
        "query": '("AI" OR "artificial intelligence") AND ("healthcare" OR "medical")',
        "description": "Nested parentheses with mixed operators",
        "expected_results": 89
    },
    {
        "name": "multiple_and_or",
        "query": '"deep learning" AND ("computer vision" OR "natural language processing" OR "speech recognition")',
        "description": "Multiple OR terms combined with AND",
        "expected_results": 134
    },
    {
        "name": "complex_nested",
        "query": '(("machine learning" OR "ML") AND "healthcare") OR (("artificial intelligence" OR "AI") AND "medical")',
        "description": "Complex nested boolean logic with multiple levels",
        "expected_results": 203
    }
]

# Field-specific boolean queries
FIELD_SPECIFIC_QUERIES = [
    {
        "name": "title_and_abstract",
        "query": 'title:"deep learning" AND abstract:"neural networks"',
        "description": "Boolean search across specific fields",
        "expected_results": 23
    },
    {
        "name": "multiple_fields",
        "query": 'title:("AI" OR "artificial intelligence") AND abstract:"healthcare" AND full_text:"machine learning"',
        "description": "Boolean search across multiple specific fields",
        "expected_results": 12
    },
    {
        "name": "field_with_complex_boolean",
        "query": 'title:(("deep learning" OR "neural networks") AND "applications") OR abstract:("computer vision" AND "medical imaging")',
        "description": "Complex boolean logic within field-specific searches",
        "expected_results": 67
    }
]

# Edge case queries
EDGE_CASE_QUERIES = [
    {
        "name": "empty_query",
        "query": "",
        "description": "Empty query string",
        "should_error": True
    },
    {
        "name": "only_operators",
        "query": "AND OR NOT",
        "description": "Query with only boolean operators",
        "should_error": True
    },
    {
        "name": "unmatched_parentheses",
        "query": '("machine learning" AND "AI"',
        "description": "Query with unmatched parentheses",
        "should_error": True
    },
    {
        "name": "special_characters",
        "query": '"machine-learning" AND "AI/ML" AND "C++"',
        "description": "Query with special characters",
        "expected_results": 15
    }
]

# Date range combined with boolean queries
DATE_RANGE_BOOLEAN_QUERIES = [
    {
        "name": "recent_ai_healthcare",
        "query": '("AI" OR "artificial intelligence") AND "healthcare"',
        "year_from": 2020,
        "year_to": 2024,
        "description": "Boolean query with recent date range",
        "expected_results": 45
    },
    {
        "name": "historical_ml",
        "query": '"machine learning" OR "neural networks"',
        "year_from": 1990,
        "year_to": 2010,
        "description": "Boolean query with historical date range",
        "expected_results": 89
    }
]


def create_user_search_input(
    query: str,
    fields: List[str] = None,
    year_from: int = None,
    year_to: int = None,
    size: int = 10,
    offset: int = 0,
    default_operator: str = "and"
) -> UserLensSearchInput:
    """Create a UserLensSearchInput for testing."""
    if fields is None:
        fields = ["title", "abstract", "full_text"]
    
    return UserLensSearchInput(
        query_string=query,
        fields=fields,
        default_operator=default_operator,
        year_from=year_from,
        year_to=year_to,
        size=size,
        offset=offset
    )


def get_all_test_queries() -> List[Dict[str, Any]]:
    """Get all test queries combined."""
    return (
        BASIC_BOOLEAN_QUERIES + 
        COMPLEX_BOOLEAN_QUERIES + 
        FIELD_SPECIFIC_QUERIES + 
        EDGE_CASE_QUERIES + 
        DATE_RANGE_BOOLEAN_QUERIES
    )


def get_valid_queries() -> List[Dict[str, Any]]:
    """Get only valid test queries (excluding error cases)."""
    return [q for q in get_all_test_queries() if not q.get("should_error", False)]


def get_error_queries() -> List[Dict[str, Any]]:
    """Get only queries that should produce errors."""
    return [q for q in get_all_test_queries() if q.get("should_error", False)]


# Pagination test scenarios
PAGINATION_TEST_CASES = [
    {
        "name": "first_page",
        "total": 100,
        "offset": 0,
        "size": 10,
        "expected_page": 1,
        "expected_total_pages": 10
    },
    {
        "name": "middle_page",
        "total": 100,
        "offset": 50,
        "size": 10,
        "expected_page": 6,
        "expected_total_pages": 10
    },
    {
        "name": "last_page",
        "total": 95,
        "offset": 90,
        "size": 10,
        "expected_page": 10,
        "expected_total_pages": 10
    },
    {
        "name": "single_result",
        "total": 1,
        "offset": 0,
        "size": 10,
        "expected_page": 1,
        "expected_total_pages": 1
    },
    {
        "name": "no_results",
        "total": 0,
        "offset": 0,
        "size": 10,
        "expected_page": 1,
        "expected_total_pages": 1
    },
    {
        "name": "large_page_size",
        "total": 50,
        "offset": 0,
        "size": 100,
        "expected_page": 1,
        "expected_total_pages": 1
    }
]