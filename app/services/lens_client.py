#!filepath: app/services/lens_client.py
from __future__ import annotations

import logging
import requests
from typing import List

from app.schemas.lens_api_request import BoolQuery, LensQuery, LensSearchRequest, QueryStringQuery, RangeQuery, SortField
from app.schemas.lens_api_response import ScholarResponse
from pydantic import ValidationError

from app.config import settings


logger = logging.getLogger(__name__)


class LensAPIClient:
    """
    Client to interact with the Lens.org scholarly search API.
    """

    def __init__(self) -> None:
        self._url = f"{settings.LENS_URL}/search"
        self._token = settings.LENS_TOKEN

    def search(self, payload: LensSearchRequest) -> List[ScholarResponse]:
        """
        Sends a search request to the Lens.org API.

        Args:
            payload (LensSearchRequest): The structured search query.

        Returns:
            List[ScholarResponse]: Parsed list of scholarly search results.
        """
        try:
            response = requests.post(
                self._url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self._token,
                },
                json=payload.dict(by_alias=True),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return [ScholarResponse(**item) for item in data.get("data", [])]
        except requests.RequestException as e:
            logger.error(f"HTTP request to Lens failed: {e}")
            raise
        except ValidationError as ve:
            logger.error(f"Response parsing failed: {ve}")
            raise


def build_example_request() -> LensSearchRequest:
    """
    Builds an example LensSearchRequest matching the provided cURL query.

    Returns:
        LensSearchRequest: The constructed request.
    """
    logger.info("Building example request...")
    
    query_string = QueryStringQuery(
        query_string={
            "query": "\"FRENCH\" OR \"ENGLISH\"",
            "fields": ["title", "abstract"],
            "default_operator": "and",
        }
    )
    logger.debug(f"Created query_string: {query_string}")

    range_query = RangeQuery(
        range={
            "year_published": {
                "gte": 1960,
                "lte": 2024
            }
        }
    )
    logger.debug(f"Created range_query: {range_query}")

    bool_query = BoolQuery(
        must=[query_string],
        filter=[range_query]
    )
    logger.debug(f"Created bool_query: {bool_query}")

    # Remove the unused LensQuery creation that was causing confusion
    # lens_query = LensQuery(__root__={"bool": bool_query})  # This was never used

    sort_fields = [
        SortField({"relevance": "desc"}),  # ✅ CORRECT
        SortField({"year_published": "desc"})
    ]
    logger.debug(f"Created sort_fields: {sort_fields}")

    request = LensSearchRequest(
        query={"bool": bool_query},
        sort=sort_fields,
        size=10,
        from_=0,
        include=["title", "abstract", "lens_id", "year_published"]
    )
    logger.info(f"Built LensSearchRequest: {request}")
    return request
