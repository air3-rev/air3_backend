from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, conint


class MatchQuery(BaseModel):
    match: Dict[str, Any]


class MatchPhraseQuery(BaseModel):
    match_phrase: Dict[str, str]


class TermQuery(BaseModel):
    term: Dict[str, Union[str, bool, int]]


class TermsQuery(BaseModel):
    terms: Dict[str, List[Union[str, int]]]


class RangeQuery(BaseModel):
    range: Dict[str, Dict[str, Union[str, int]]]


class QueryStringQuery(BaseModel):
    query_string: Dict[str, Any]


class BoolQuery(BaseModel):
    must: Optional[List[Union[MatchQuery, MatchPhraseQuery, TermQuery, TermsQuery, QueryStringQuery, RangeQuery, BoolQuery]]] = None
    should: Optional[List[Any]] = None
    must_not: Optional[List[Any]] = None
    filter: Optional[List[Any]] = None


class LensQuery(BaseModel):
    query: Union[
        MatchQuery,
        MatchPhraseQuery,
        TermQuery,
        TermsQuery,
        RangeQuery,
        QueryStringQuery,
        Dict[str, BoolQuery],
        Dict[str, str],
    ]


from typing import Literal, Dict
from pydantic import RootModel

class SortField(RootModel[Dict[str, Literal["asc", "desc"]]]):
    pass

# In app/schemas/lens_api_request.py
from pydantic import BaseModel, Field
from typing import Union

class LensSearchRequest(BaseModel):
    """
    Represents a request payload to the Lens.org API search endpoint.
    """

    query: Union[
        MatchQuery,
        MatchPhraseQuery,
        TermQuery,
        TermsQuery,
        RangeQuery,
        QueryStringQuery,
        Dict[str, BoolQuery],
        Dict[str, str],
    ]
    sort: Optional[List[SortField]] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    size: Optional[conint(gt=0)] = Field(default=20, description="Number of items per page")
    from_: Optional[conint(ge=0)] = Field(default=0, alias="from", description="Offset from first result")
    scroll_id: Optional[str] = None
    scroll: Optional[str] = None  # e.g. "1m"
    stemming: Optional[bool] = True
    regex: Optional[bool] = False
    min_score: Optional[float] = None

    class Config:
        populate_by_name = True
        str_strip_whitespace = True
