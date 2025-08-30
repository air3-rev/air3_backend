"""Provides API endpoints to ingest data from external sources into the vector database."""

import logging
from typing import Any, List

from dotenv import load_dotenv

# import tiktoken
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.data_ingestion.types import PdfDocument

logger = logging.getLogger(__name__)

load_dotenv()

CHUNK_SIZE = 1000
EMBED_MODEL = "text-embedding-3-large"
embeddings_model = OpenAIEmbeddings(model=EMBED_MODEL)


# def tiktoken_len(text: str) -> int:
#     # Token counter for chunking (OpenAI cl100k_base fits most modern models)
#     enc = tiktoken.get_encoding("cl100k_base")
#     return len(enc.encode(text))


def chunk_document(pdfDocument: PdfDocument) -> List[str]:
    """Chunk text into smaller pieces of specified size."""
    chunker = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,  # tokens, not characters
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
