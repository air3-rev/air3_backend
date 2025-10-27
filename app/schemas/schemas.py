from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


# Base schemas
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


# Search scope generation schemas
class GenerateSearchScopeInput(BaseModel):
    review_id: str
    review_title: Optional[str] = None
    review_description: Optional[str] = None
    keyword_groups: Optional[List[Dict[str, Any]]] = None


class SearchScopeFilters(BaseModel):
    publication_types: Optional[List[str]] = None
    open_access_only: Optional[bool] = None
    date_range: Optional[Dict[str, str]] = None
    field_of_study: Optional[List[str]] = None
    journal_tier: Optional[List[str]] = None
    min_citations: Optional[int] = None
    sort_by: Optional[str] = None
    search_fields: Optional[List[str]] = None
    ranking: Optional[str] = None


class GenerateSearchScopeResponse(BaseModel):
    success: bool
    filters: SearchScopeFilters
    reasoning: Optional[str] = None


# Generic response schemas
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    message: str
    status_code: int