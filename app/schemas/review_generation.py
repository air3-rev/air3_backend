from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class GenerateSectionRequest(BaseModel):
    """Request model for generating a section or subsection of the literature review."""
    review_id: str = Field(..., description="UUID of the review")
    section_id: str = Field(..., description="UUID of the section to generate content for")
    subsection_id: Optional[str] = Field(None, description="UUID of the subsection (if generating subsection content)")
    previous_content: Optional[Dict[str, Any]] = Field(None, description="Content from previous sections/subsections for context")


class GenerateSectionResponse(BaseModel):
    """Response model for section/subsection generation."""
    content: str = Field(..., description="Generated content for the section or subsection")
    section_id: str = Field(..., description="UUID of the section")
    subsection_id: Optional[str] = Field(None, description="UUID of the subsection (if applicable)")
    generated_at: datetime = Field(default_factory=datetime.now, description="Timestamp of generation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the generation")


class SectionData(BaseModel):
    """Data structure for section information used in generation."""
    id: str
    title: str
    description: str
    subsections: List[Dict[str, str]] = Field(default_factory=list)  # List of {id: str, title: str, description: str}


class PaperExtractedData(BaseModel):
    """Extracted data from a paper for a specific label."""
    paper_id: str
    label_name: str
    data: Dict[str, Any]
    created_at: datetime


class SectionContext(BaseModel):
    """Context information for generating a section."""
    section: SectionData
    assigned_papers: List[str] = Field(default_factory=list, description="List of paper IDs assigned to this section")
    extracted_data: List[PaperExtractedData] = Field(default_factory=list, description="Extracted data from assigned papers")
    previous_sections_content: Dict[str, str] = Field(default_factory=dict, description="Content from previous sections")
    previous_subsections_content: Dict[str, str] = Field(default_factory=dict, description="Content from previous subsections in same section")


class SubsectionContext(BaseModel):
    """Context information for generating a subsection."""
    section: SectionData
    subsection: Dict[str, str]  # {id: str, title: str, description: str}
    assigned_papers: List[str] = Field(default_factory=list, description="List of paper IDs assigned to this section")
    extracted_data: List[PaperExtractedData] = Field(default_factory=list, description="Extracted data from assigned papers")
    section_content: str = Field("", description="Content already generated for the parent section")
    previous_subsections_content: Dict[str, str] = Field(default_factory=dict, description="Content from previous subsections in same section")