import logging
from typing import List

import fitz  # PyMuPDF
from fastapi import HTTPException, UploadFile

from app.services.data_ingestion.types import PdfDocument, PdfFile

logger = logging.getLogger(__name__)


def read_pdf_file(file: UploadFile) -> PdfFile:
    """Read and extract text from a PDF UploadFile.

    Returns:
        PdfFile
    """
    try:
        raw = file.file.read()
        if not raw:
            raise ValueError("Empty upload.")
        with fitz.open(stream=raw, filetype="pdf") as doc:
            texts: List[str] = []
            for page in doc:
                # blocks keeps layout; get_text("text") is simpler but may merge poorly
                blocks = page.get_text("blocks")
                page_text_parts = [
                    b[4] for b in blocks if isinstance(b[4], str) and b[4].strip()
                ]
                page_text = "\n".join(page_text_parts).strip()
                # Fallback: if page has no block text, try a simpler extractor
                if not page_text:
                    page_text = page.get_text("text").strip()
                texts.append(page_text)
            combined = "\n\n".join([t for t in texts if t])
            return PdfFile(raw_content=raw, content=combined, length=len(doc))
    except Exception as e:
        logger.exception("Failed to parse PDF")
        raise HTTPException(
            status_code=400, detail=f"Invalid or unreadable PDF: {e}"
        ) from e


def parse_pdf_into_document(file: PdfFile) -> PdfDocument:
    """Normalize text for downstream chunking.

    No pre-processing for now.
    """
    if not file.content or not file.content.strip():
        raise HTTPException(
            status_code=400, detail="The PDF contains no readable text."
        )
    return PdfDocument(content=file.content)
