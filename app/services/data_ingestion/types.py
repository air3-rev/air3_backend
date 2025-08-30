from typing import Optional

from pydantic import BaseModel


class PdfFile(BaseModel):
    raw_content: Optional[bytes]
    content: Optional[str]
    length: Optional[int]


class PdfDocument(BaseModel):
    """Represents a parsed PDF document."""

    content: str
    title: Optional[str] = None
    author: Optional[str] = None
    num_pages: Optional[int] = None
