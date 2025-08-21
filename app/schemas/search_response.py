from typing import List, Optional
from pydantic import BaseModel, Field
from math import ceil

from app.schemas.lens_api_response import ScholarResponse


class PaginationMetadata(BaseModel):
    """Pagination metadata for search results"""
    total: int = Field(..., description="Total number of results matching the query")
    page: int = Field(..., description="Current page number (1-based)")
    size: int = Field(..., description="Number of results per page")
    total_pages: int = Field(..., description="Total number of pages")

    @classmethod
    def create(cls, total: int, offset: int, size: int) -> "PaginationMetadata":
        """Create pagination metadata from offset-based parameters"""
        current_page = (offset // size) + 1 if size > 0 else 1
        total_pages = ceil(total / size) if size > 0 and total > 0 else 1
        
        return cls(
            total=total,
            page=current_page,
            size=size,
            total_pages=total_pages
        )


class EnrichedSearchResponse(BaseModel):
    """Enriched search response with pagination metadata and max score"""
    data: List[ScholarResponse] = Field(..., description="List of scholarly articles")
    pagination: PaginationMetadata = Field(..., description="Pagination information")
    max_score: Optional[float] = Field(None, description="Maximum relevance score in the result set")


class LensAPIFullResponse(BaseModel):
    """Complete response structure from Lens API"""
    total: int = Field(..., description="Total number of results")
    max_score: Optional[float] = Field(None, description="Maximum relevance score")
    data: List[dict] = Field(..., description="Raw article data from API")