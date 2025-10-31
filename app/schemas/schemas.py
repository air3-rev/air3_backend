from typing import List, Optional
from pydantic import BaseModel
from app.schemas.lens_api_response import ScholarResponse

class GenerateSearchScopeInput(BaseModel):
    review_id: str
    review_title: Optional[str] = None
    review_description: Optional[str] = None
    keyword_groups: Optional[List[dict]] = None

class GenerateSearchScopeResponse(BaseModel):
    success: bool
    filters: dict
    reasoning: str

class FetchByDoisInput(BaseModel):
    dois: List[str] = []

class FetchByDoisResponse(BaseModel):
    data: List[ScholarResponse]
    found_count: int
    not_found_count: int
    not_found_dois: List[str]