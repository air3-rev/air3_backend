"""Mock Lens API responses for testing."""

from typing import Dict, Any, List


def get_mock_lens_api_response(total: int = 81, max_score: float = 18.112701) -> Dict[str, Any]:
    """Generate a mock Lens API response with realistic data."""
    return {
        "total": total,
        "max_score": max_score,
        "data": [
            {
                "lens_id": "002-534-152-232-951",
                "title": "Skill ontology for Mechanical Design : Application to e-learning system",
                "publication_type": "journal article",
                "year_published": 2006,
                "date_published_parts": [2006],
                "abstract": "This paper presents a skill ontology for mechanical design that can be applied to e-learning systems.",
                "authors": [
                    {
                        "collective_name": None,
                        "first_name": "John",
                        "last_name": "Smith",
                        "initials": "J.S.",
                        "affiliations": [
                            {
                                "name": "University of Technology",
                                "name_original": None,
                                "grid_id": None,
                                "country_code": "US",
                                "ids": None
                            }
                        ],
                        "ids": None
                    }
                ],
                "source": {
                    "title": "International Journal of Engineering Education",
                    "type": "journal",
                    "publisher": "Academic Press",
                    "issn": None,
                    "country": None,
                    "asjc_codes": None,
                    "asjc_subjects": None
                }
            },
            {
                "lens_id": "003-645-263-343-062",
                "title": "Machine Learning Applications in Healthcare Systems",
                "publication_type": "journal article",
                "year_published": 2020,
                "date_published_parts": [2020],
                "abstract": "A comprehensive review of machine learning applications in modern healthcare systems.",
                "authors": [
                    {
                        "collective_name": None,
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "initials": "J.D.",
                        "affiliations": [
                            {
                                "name": "Medical Research Institute",
                                "name_original": None,
                                "grid_id": None,
                                "country_code": "UK",
                                "ids": None
                            }
                        ],
                        "ids": None
                    }
                ],
                "source": {
                    "title": "Journal of Medical Informatics",
                    "type": "journal",
                    "publisher": "Elsevier",
                    "issn": None,
                    "country": None,
                    "asjc_codes": None,
                    "asjc_subjects": None
                }
            }
        ]
    }


def get_empty_lens_api_response() -> Dict[str, Any]:
    """Generate an empty Lens API response."""
    return {
        "total": 0,
        "max_score": None,
        "data": []
    }


def get_single_result_response() -> Dict[str, Any]:
    """Generate a Lens API response with a single result."""
    return {
        "total": 1,
        "max_score": 15.5,
        "data": [
            {
                "lens_id": "001-123-456-789-000",
                "title": "Boolean Search in Academic Databases",
                "publication_type": "conference proceedings article",
                "year_published": 2023,
                "date_published_parts": [2023],
                "abstract": "This study explores the effectiveness of boolean search operators in academic database queries.",
                "authors": [
                    {
                        "collective_name": None,
                        "first_name": "Alice",
                        "last_name": "Johnson",
                        "initials": "A.J.",
                        "affiliations": [
                            {
                                "name": "Search Technology Lab",
                                "name_original": None,
                                "grid_id": None,
                                "country_code": "CA",
                                "ids": None
                            }
                        ],
                        "ids": None
                    }
                ],
                "source": None
            }
        ]
    }


def get_large_dataset_response(total: int = 1000) -> Dict[str, Any]:
    """Generate a Lens API response simulating a large dataset."""
    return {
        "total": total,
        "max_score": 22.8,
        "data": [
            {
                "lens_id": f"00{i}-{i*100}-{i*200}-{i*300}-{i*400}",
                "title": f"Research Article {i+1}: Advanced Topics in Computer Science",
                "publication_type": "journal article",
                "year_published": 2020 + (i % 4),
                "date_published_parts": [2020 + (i % 4)],
                "abstract": f"This is the abstract for research article {i+1} covering advanced computer science topics.",
                "authors": None,
                "source": None
            }
            for i in range(min(20, total))  # Return up to 20 items per page
        ]
    }


# Boolean search specific mock responses
BOOLEAN_SEARCH_RESPONSES = {
    "simple_and": {
        "query": '"machine learning" AND "healthcare"',
        "response": {
            "total": 45,
            "max_score": 19.2,
            "data": [
                {
                    "lens_id": "bool-001-and-test",
                    "title": "Machine Learning Applications in Healthcare",
                    "publication_type": "journal article",
                    "year_published": 2022,
                    "abstract": "This paper explores machine learning techniques applied to healthcare systems.",
                    "authors": None,
                    "source": None
                }
            ]
        }
    },
    "simple_or": {
        "query": '"python" OR "javascript"',
        "response": {
            "total": 156,
            "max_score": 16.8,
            "data": [
                {
                    "lens_id": "bool-002-or-test",
                    "title": "Comparative Analysis of Python and JavaScript",
                    "publication_type": "conference proceedings article",
                    "year_published": 2023,
                    "abstract": "A detailed comparison between Python and JavaScript programming languages.",
                    "authors": None,
                    "source": None
                }
            ]
        }
    },
    "complex_nested": {
        "query": '("AI" OR "artificial intelligence") AND ("healthcare" OR "medical")',
        "response": {
            "total": 89,
            "max_score": 21.5,
            "data": [
                {
                    "lens_id": "bool-003-complex-test",
                    "title": "Artificial Intelligence in Medical Diagnosis",
                    "publication_type": "journal article",
                    "year_published": 2023,
                    "abstract": "Advanced AI techniques for improving medical diagnosis accuracy.",
                    "authors": None,
                    "source": None
                }
            ]
        }
    },
    "field_specific": {
        "query": 'title:"deep learning" AND abstract:"neural networks"',
        "response": {
            "total": 23,
            "max_score": 24.1,
            "data": [
                {
                    "lens_id": "bool-004-field-test",
                    "title": "Deep Learning Architectures for Complex Problems",
                    "publication_type": "journal article",
                    "year_published": 2023,
                    "abstract": "This paper presents novel neural networks architectures for deep learning applications.",
                    "authors": None,
                    "source": None
                }
            ]
        }
    }
}


def get_boolean_search_response(query_type: str) -> Dict[str, Any]:
    """Get a mock response for a specific boolean search type."""
    response_data = BOOLEAN_SEARCH_RESPONSES.get(query_type, {"response": get_mock_lens_api_response()})
    # Return the actual response data, not the wrapper
    if isinstance(response_data, dict) and "response" in response_data:
        return response_data["response"]
    return response_data


# Error responses for testing error handling
def get_api_error_response() -> Dict[str, Any]:
    """Generate a mock API error response."""
    return {
        "error": "Invalid query syntax",
        "message": "The provided query contains invalid boolean operators",
        "status_code": 400
    }


def get_timeout_error_response() -> Dict[str, Any]:
    """Generate a mock timeout error response."""
    return {
        "error": "Request timeout",
        "message": "The request took too long to process",
        "status_code": 408
    }