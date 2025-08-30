"""Provides API endpoints to ingest data from external sources into the vector database."""

import logging
from typing import Any, List, Optional

import fitz  # PyMuPDF
from dotenv import load_dotenv

# import tiktoken
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db

load_dotenv()
router = APIRouter()
logger = logging.getLogger(__name__)


CHUNK_SIZE = 500
EMBED_MODEL = "text-embedding-3-large"
embeddings_model = OpenAIEmbeddings(model=EMBED_MODEL)


class PdfDocument(BaseModel):
    """Represents a parsed PDF document."""

    content: str
    title: Optional[str] = None
    author: Optional[str] = None
    num_pages: Optional[int] = None


class PdfFile(BaseModel):
    raw_content: Optional[bytes]
    content: Optional[str]
    length: Optional[int]


# class Embedding(BaseModel):
#     """Represents a parsed PDF document."""

#     embedding: List[float]
#     metadata: dict


# def tiktoken_len(text: str) -> int:
#     # Token counter for chunking (OpenAI cl100k_base fits most modern models)
#     enc = tiktoken.get_encoding("cl100k_base")
#     return len(enc.encode(text))


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


def chunk_document(pdfDocument: PdfDocument) -> List[str]:
    """Chunk text into smaller pieces of specified size."""
    chunker = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # tokens, not characters
        chunk_overlap=200,  # 20% overlap for context preservation
        # length_function=tiktoken_len,  # token-based counting
        separators=[
            "\n\n",  # paragraphs first
            "\n",  # then lines
            ". ",  # sentences
            " ",  # words
            "",  # characters (last resort)
        ],
    )
    chunks = chunker.split_text(pdfDocument.content)

    logger.info("CHUUUUNKS {}", chunks)

    return chunks


def embed_chunks(chunks: List[str], batch_size: int = 90) -> Any:
    """Embed text chunks into vector representations. Use OpenAI"""
    if not chunks:
        return []
    vectors: List[List[float]] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vectors.extend(embeddings_model.embed_documents(batch))

    logger.info("VECTORS: {}", vectors)
    return vectors


def store_in_vector_db(embeddings: List[Any]):
    """Store embeddings and metadata in the vector database."""
    pass


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_file(
    file: UploadFile = File(..., description="A single PDF file"),
    db: Session = Depends(get_db),
):
    pdf_file: PdfFile = read_pdf_file(file)
    pdf_doc: PdfDocument = parse_pdf_into_document(pdf_file)
    document_chunks: List[str] = chunk_document(pdf_doc)
    logger.info("Document CHUNKS : ", document_chunks)
    logger.info("Baby, I'm-a want you !")
    embeddings: List[Any] = embed_chunks(document_chunks)

    logger.info("Embedings: {}", embeddings)
    # store_in_vector_db(embeddings)


# @router.get("/extract-data")
# async def extract_data_from_file(
#     file: File,
#     extract_label: str,
#     db: Session = Depends(get_db),
# ):
#     """Extract data from a file based on user input, and return information."""
#     pass
