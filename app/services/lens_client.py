#!filepath: app/services/lens_client.py
from __future__ import annotations
import json
import logging
import httpx
from typing import List, Optional, Union, Any

from app.schemas.lens_api_request import LensSearchRequest, UserLensSearchInput
from app.schemas.lens_api_response import PublicationType
from app.schemas.search_response import LensAPIFullResponse
from pydantic import ValidationError

from app.config import settings
from app.services.journals import get_issns


logger = logging.getLogger(__name__)


class LensAPIClient:
    """
    Client to interact with the Lens.org scholarly search API.
    """

    def __init__(self) -> None:
        self._url = f"{settings.lens_url}/search"
        self._token = settings.lens_token

    def search(self, payload: Union[LensSearchRequest, dict]) -> LensAPIFullResponse:
        """
        Sends a search request to the Lens.org API.

        Args:
            payload (LensSearchRequest): The structured search query.

        Returns:
            LensAPIFullResponse: Complete API response with total, max_score, and data.
        """
        try:            
            response = httpx.post(
                self._url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
                json=payload,
                timeout=60,
            )
            
            # logger.info(f"Response status: {response.status_code}")
            if not response.ok:
                logger.error(f"Response body: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Extract the complete response structure
            return LensAPIFullResponse(
                total=data.get("total", 0),
                max_score=data.get("max_score"),
                data=data.get("data", [])
            )
        except httpx.RequestError as e:
            logger.error(f"HTTP request to Lens failed: {e}")
            raise
        except ValidationError as ve:
            logger.error(f"Response parsing failed: {ve}")
            raise



publication_type_mapping = {
            PublicationType.JournalArticle: "journal article",
            PublicationType.Review: "journal article",
            PublicationType.Book: "book",
            PublicationType.BookChapter: "book chapter",
            PublicationType.Conference: "conference proceedings",
            PublicationType.ConferenceArticle: "conference proceedings article",
            PublicationType.Dataset: "dataset",
            PublicationType.ReferenceEntry: "reference entry",
            PublicationType.Guide: "libguide",
            PublicationType.Other: "component"
        }

def build_lens_request_v2(user_input: UserLensSearchInput):
    size = min(user_input.size or 10, 100)  # Cap at 100
    offset = max(user_input.offset or 0, 0)  # Ensure non-negative

    sort = []
    if user_input.sort_by:
        for sort_item in user_input.sort_by:
            try:
                # Ensure the sort item is in the correct format
                if isinstance(sort_item, dict) and len(sort_item) == 1:
                    sort.append(sort_item)  # Use the dictionary directly
                else:
                    logger.warning(f"Invalid sort format: {sort_item}, using default")
                    sort.append({"relevance": "desc"})  # Plain dictionary
            except Exception as e:
                logger.warning(f"Failed to create sort field from {sort_item}: {e}")
                sort.append({"relevance": "desc"})  # Plain dictionary

    # Fetch ISSNs based on journal_tier and fields_of_study if provided
    accepted_issns = user_input.accepted_issns or []
    if user_input.journal_tier:
        # Uppercase quartiles to match database values (Q1, Q2, etc.)
        quartiles = [tier.upper() for tier in user_input.journal_tier]
        fields = user_input.fields_of_study or []

        issns = get_issns(fields=fields, quartiles=quartiles)
        accepted_issns.extend(issns)
        # Remove duplicates
        accepted_issns = list(set(accepted_issns))

    filter_clauses = []

    if user_input.year_from or user_input.year_to:

        range_clause = {
            "year_published": {}
        }

        if user_input.year_from:
            range_clause["year_published"]["gte"] = user_input.year_from
        if user_input.year_to:
            range_clause["year_published"]["lte"] = user_input.year_to

        range_filter = {
            "range": range_clause
        }
        filter_clauses.append(range_filter)

    query_string = user_input.query_string.strip()
    if not query_string:
        query_string = '"research"'  # Fallback query
        logger.warning("Empty query string provided, using fallback")
    # else: 
        # query_string = query_string.replace('"', "'")


    query_clause = {
        "query_string": {
            "query": query_string,
            "fields": user_input.fields,
            "default_operator": user_input.default_operator
        }
    }
    must_clauses = [query_clause]
    # Add open access filter if requested
    if user_input.open_access_only:
        must_clauses.append({"match": {"is_open_access": user_input.open_access_only}})

    should_clauses = []
    if user_input.publication_types:
        for pub_type in user_input.publication_types:
            search_term = publication_type_mapping.get(pub_type, pub_type.value.lower())
            should_clauses.append({
                "match": {
                    "publication_type": search_term
                }
            })

        pub_type_bool = {
            "bool": {
                "should": should_clauses
            }
        }
        must_clauses.append(pub_type_bool)
    # Add ISSN filter if requested
    if accepted_issns:
        logger.info(f"Adding ISSN filter with {len(accepted_issns)} ISSNs: {accepted_issns[:5]}...")
        issn_terms = {
            "terms": {
                "source.issn": accepted_issns
            }
        }
        must_clauses.append(issn_terms)
    else:
        logger.info("No accepted_issns provided, skipping ISSN filter")

    query_dict = {
        "bool": {
            "must": must_clauses,
            "filter": filter_clauses
        }
    }

    payload = {
        "query" : query_dict,
        "sort": sort,
        "include": user_input.include_fields,
        "size": size,
        "from":offset
    }
    return payload

def build_lens_id_search_request(lens_ids: List[str], include_fields: Optional[List[str]] = None) -> dict:
    """
    Build a Lens API request to search for papers by Lens IDs.

    Args:
        lens_ids: List of Lens ID strings to search for
        include_fields: Optional list of fields to include in response

    Returns:
        Dict containing the search request payload
    """
    if not include_fields:
        include_fields = [
            "title",
            "open_access",
            "abstract",
            "lens_id",
            "year_published",
            "source_urls",
            "scholarly_citations_count",
            "authors",
            "external_ids",
            "references",
            "references_count",
            "references_resolved_count",
            "source"
        ]

    # Clean lens_ids
    cleaned_lens_ids = [lid.strip() for lid in lens_ids if lid.strip()]

    query_dict = {
        "bool": {
            "must": [
                {
                    "terms": {
                        "lens_id": cleaned_lens_ids
                    }
                }
            ]
        }
    }

    payload = {
        "query": query_dict,
        "include": include_fields,
        "size": min(len(cleaned_lens_ids), 1000),  # API max is 1000
        "from": 0
    }

    logger.info(f"Lens ID search payload: {json.dumps(payload, indent=2)}")

    return payload


def build_doi_search_request(dois: List[str], include_fields: Optional[List[str]] = None) -> dict:
    """
    Build a Lens API request to search for papers by DOI numbers.

    Args:
        dois: List of DOI strings to search for
        include_fields: Optional list of fields to include in response

    Returns:
        Dict containing the search request payload
    """
    if not include_fields:
        include_fields = [
            "title",
            "open_access",
            "abstract",
            "lens_id",
            "year_published",
            "source_urls",
            "scholarly_citations_count",
            "authors",
            "external_ids",
            "references",
            "references_count",
            "references_resolved_count",
            "source"
        ]

    # Clean and normalize DOIs - keep original case as Lens API is case-sensitive for DOIs
    cleaned_dois = [
        doi.replace("\\/", "/").strip()
        for doi in dois
    ]

    # Use the correct Lens API field path for DOI search
    query_dict = {
        "terms": {
            "ids.doi": cleaned_dois
        }
    }

    payload = {
        "query": query_dict,
        "include": include_fields,
        "size": min(len(dois), 1000),  # API max is 1000
        "from": 0
    }

    logger.info(f"DOI search payload: {json.dumps(payload, indent=2)}")

    return payload