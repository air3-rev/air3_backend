from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Union, Any

from pydantic import BaseModel, Field, validator


class PublicationType(str, Enum):
    JOURNAL_ARTICLE = "journal article"
    LETTER = "letter"
    EDITORIAL = "editorial"
    NEWS = "news"
    BOOK = "book"
    BOOK_CHAPTER = "book chapter"
    CONFERENCE_PROCEEDINGS_ARTICLE = "conference proceedings article"
    CONFERENCE_PROCEEDINGS = "conference proceedings"
    DATASET = "dataset"
    JOURNAL = "journal"
    JOURNAL_ISSUE = "journal issue"
    JOURNAL_VOLUME = "journal volume"
    REPORT = "report"
    STANDARD = "standard"
    DISSERTATION = "dissertation"
    CLINICAL_TRIAL = "clinical trial"
    CLINICAL_STUDY = "clinical study"
    LIBGUIDE = "libguide"
    REFERENCE_ENTRY = "reference entry"
    WORKING_PAPER = "working paper"
    COMPONENT = "component"
    REVIEW = "review"
    PREPRINT = "preprint"
    OTHER = "other"
    UNKNOWN = "unknown"


class Ids(BaseModel):
    type: str
    value: str


class Affiliation(BaseModel):
    name: Optional[str] = None
    name_original: Optional[str] = None
    grid_id: Optional[str] = None
    country_code: Optional[str] = None
    ids: Optional[List[Ids]] = None


class Author(BaseModel):
    collective_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    initials: Optional[str] = None
    affiliations: Optional[List[Affiliation]] = None
    ids: Optional[List[Ids]] = None


class Reference(BaseModel):
    lens_id: Optional[str] = None
    text: Optional[str] = None


class PatentCitation(BaseModel):
    lens_id: str


class Chemical(BaseModel):
    mesh_id: Optional[str] = None
    registry_number: Optional[str] = None
    substance_name: Optional[str]


class ClinicalTrial(BaseModel):
    id: Optional[str] = None
    registry: Optional[str]


class SourceUrl(BaseModel):
    type: Optional[str] = None
    url: Optional[str]


class Conference(BaseModel):
    name: Optional[str] = None
    instance: Optional[str] = None
    location: Optional[str]


class OpenAccessLocation(BaseModel):
    landing_page_urls: Optional[List[str]]
    pdf_urls: Optional[List[str]]


class OpenAccess(BaseModel):
    license: Optional[str] = None
    colour: Optional[str] = None
    locations: Optional[List[OpenAccessLocation]]


class Issn(BaseModel):
    value: Optional[str] = None
    type: Optional[str]


class Source(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    publisher: Optional[str] = None
    issn: Optional[List[Issn]] = None
    country: Optional[str] = None
    asjc_codes: Optional[Union[str, List[str]]] = None
    asjc_subjects: Optional[Union[str, List[str]]] = None
    
    @validator('asjc_codes', pre=True)
    def validate_asjc_codes(cls, v):
        """Convert list to string if needed"""
        if isinstance(v, list):
            return ",".join(str(item) for item in v)
        return v
    
    @validator('asjc_subjects', pre=True)
    def validate_asjc_subjects(cls, v):
        """Convert list to string if needed"""
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        return v


class MeshTerm(BaseModel):
    mesh_id: Optional[str] = None
    mesh_heading: Optional[str] = None
    qualifier_id: Optional[str] = None
    qualifier_name: Optional[str]


class Funding(BaseModel):
    org: Optional[str] = None
    funding_id: Optional[str] = None
    country: Optional[str]


class RetractionUpdate(BaseModel):
    updated: Optional[date]
    update_nature: Optional[str] = None
    reasons: Optional[List[str]]
    notes: Optional[str] = None
    urls: Optional[List[str]]


class ScholarResponse(BaseModel):
    lens_id: Optional[str] = None
    created: Optional[datetime] = None
    publication_type: Optional[PublicationType] = None
    publication_supplementary_type: Optional[List[str]] = None
    authors: Optional[List[Author]] = None
    title: Optional[str] = None
    external_ids: Optional[List[Ids]] = None
    start_page: Optional[str] = None
    end_page: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    languages: Optional[List[str]] = None
    references: Optional[List[Reference]] = None
    references_count: Optional[int] = None
    references_resolved_count: Optional[int] = None
    scholarly_citations: Optional[List[str]] = None
    scholarly_citations_count: Optional[int] = None
    patent_citations: Optional[List[PatentCitation]] = None
    patent_citations_count: Optional[int] = None
    chemicals: Optional[List[Chemical]] = None
    clinical_trials: Optional[List[ClinicalTrial]] = None
    fields_of_study: Optional[List[str]] = None
    source_urls: Optional[List[SourceUrl]] = None
    abstract: Optional[str] = None
    date_published: Optional[date] = None
    date_published_parts: Optional[List[int]] = None
    year_published: Optional[int] = None
    conference: Optional[Conference] = None
    author_count: Optional[int] = None
    open_access: Optional[OpenAccess] = None
    source: Optional[Source] = None
    keywords: Optional[List[str]] = None
    mesh_terms: Optional[List[MeshTerm]] = None
    funding: Optional[List[Funding]] = None
    retraction_updates: Optional[List[RetractionUpdate]] = None

