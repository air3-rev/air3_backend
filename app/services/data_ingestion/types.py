from typing import Any, Dict, Optional

from pydantic import BaseModel


class PdfFile(BaseModel):
    file_name: str = "file.pdf"
    raw_content: bytes
    content: Optional[str]
    length: Optional[int]


class PdfDocument(BaseModel):
    """Represents a parsed PDF document."""

    doc_id: str
    content: str
    file_name: str = "file.pdf"
    title: Optional[str] = None
    author: Optional[str] = None
    num_pages: Optional[int] = None


class Chunk(BaseModel):
    id: Optional[str]
    text: str
    metadata: Dict[str, Any]
    similarity: float