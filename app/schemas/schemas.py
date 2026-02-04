from typing import List, Optional
from pydantic import BaseModel, Field
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

class FetchByLensIdsInput(BaseModel):
    lens_ids: List[str] = []

class FetchByLensIdsResponse(BaseModel):
    data: List[ScholarResponse]
    found_count: int
    not_found_count: int
    not_found_lens_ids: List[str]
    
class DownloadPdfRequest(BaseModel):
    paper_id: str = Field(..., description="UUID of the paper")
    pdf_url: str = Field(..., description="URL of the PDF to download")
    user_id: str = Field(..., description="User ID for storage path")
    review_id: str = Field(..., description="Review ID for storage path")