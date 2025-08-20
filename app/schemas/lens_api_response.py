from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


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
    name: Optional[str]
    name_original: Optional[str]
    grid_id: Optional[str]
    country_code: Optional[str]
    ids: Optional[List[Ids]]


class Author(BaseModel):
    collective_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    initials: Optional[str]
    affiliations: Optional[List[Affiliation]]
    ids: Optional[List[Ids]]


class Reference(BaseModel):
    lens_id: Optional[str]
    text: Optional[str]


class PatentCitation(BaseModel):
    lens_id: str


class Chemical(BaseModel):
    mesh_id: Optional[str]
    registry_number: Optional[str]
    substance_name: Optional[str]


class ClinicalTrial(BaseModel):
    id: Optional[str]
    registry: Optional[str]


class SourceUrl(BaseModel):
    type: Optional[str]
    url: Optional[str]


class Conference(BaseModel):
    name: Optional[str]
    instance: Optional[str]
    location: Optional[str]


class OpenAccessLocation(BaseModel):
    landing_page_urls: Optional[List[str]]
    pdf_urls: Optional[List[str]]


class OpenAccess(BaseModel):
    license: Optional[str]
    colour: Optional[str]
    locations: Optional[List[OpenAccessLocation]]


class Issn(BaseModel):
    value: Optional[str]
    type: Optional[str]


class Source(BaseModel):
    title: Optional[str]
    type: Optional[str]
    publisher: Optional[str]
    issn: Optional[List[Issn]]
    country: Optional[str]
    asjc_codes: Optional[str]
    asjc_subjects: Optional[str]


class MeshTerm(BaseModel):
    mesh_id: Optional[str]
    mesh_heading: Optional[str]
    qualifier_id: Optional[str]
    qualifier_name: Optional[str]


class Funding(BaseModel):
    org: Optional[str]
    funding_id: Optional[str]
    country: Optional[str]


class RetractionUpdate(BaseModel):
    updated: Optional[date]
    update_nature: Optional[str]
    reasons: Optional[List[str]]
    notes: Optional[str]
    urls: Optional[List[str]]


class ScholarResponse(BaseModel):
    lens_id: str
    created: Optional[datetime]
    publication_type: Optional[PublicationType]
    publication_supplementary_type: Optional[List[str]]
    authors: Optional[List[Author]]
    title: Optional[str]
    external_ids: Optional[List[Ids]]
    start_page: Optional[str]
    end_page: Optional[str]
    volume: Optional[str]
    issue: Optional[str]
    languages: Optional[List[str]]
    references: Optional[List[Reference]]
    references_count: Optional[int]
    references_resolved_count: Optional[int]
    scholarly_citations: Optional[List[str]]
    scholarly_citations_count: Optional[int]
    patent_citations: Optional[List[PatentCitation]]
    patent_citations_count: Optional[int]
    chemicals: Optional[List[Chemical]]
    clinical_trials: Optional[List[ClinicalTrial]]
    fields_of_study: Optional[List[str]]
    source_urls: Optional[List[SourceUrl]]
    abstract: Optional[str]
    date_published: Optional[date]
    date_published_parts: Optional[List[int]]
    year_published: Optional[int]
    conference: Optional[Conference]
    author_count: Optional[int]
    open_access: Optional[OpenAccess]
    source: Optional[Source]
    keywords: Optional[List[str]]
    mesh_terms: Optional[List[MeshTerm]]
    funding: Optional[List[Funding]]
    retraction_updates: Optional[List[RetractionUpdate]]

