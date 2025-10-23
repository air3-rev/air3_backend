"""Provides API endpoints to ingest data from external sources into the vector database."""

from http.client import HTTPException
import logging

# import tiktoken
from app.services.data_extraction.fetch import _get_supabase
from fastapi import UploadFile

from app.services.data_ingestion.process import chunk_document
from app.services.data_ingestion.read import parse_pdf_into_document, read_paper_pdf_file, read_pdf_file
from app.services.data_ingestion.store import store_in_vector_db

logger = logging.getLogger(__name__)


# def ingest_file(file: UploadFile):
#     pdf_file = read_pdf_file(file)
#     pdf_doc = parse_pdf_into_document(pdf_file)
#     document_chunks = chunk_document(pdf_doc)
#     store_in_vector_db(document_chunks)



def ingest_paper(pdf_bytes: bytes, paper_id: str):
    """
    Ingest a paper PDF into paper_chunks, linked by paper_id.
    """
    # 1️⃣ Parse PDF
    pdf_file = read_paper_pdf_file(pdf_bytes, filename=f"{paper_id}.pdf")

    pdf_doc = parse_pdf_into_document(pdf_file)

    # 2️⃣ Chunk PDF
    document_chunks = chunk_document(pdf_doc)

    # 3️⃣ Attach paper_id
    for doc in document_chunks:
        doc.metadata['paper_id'] = paper_id

    # 4️⃣ Store chunks in Supabase
    store_in_vector_db(document_chunks)
    
    
def download_pdf_from_storage(storage_path: str) -> bytes:
    """
    Download a PDF from the Supabase 'papers_pdf' bucket.
    """
    sb = _get_supabase()
    res = sb.storage.from_("papers_pdf").download(storage_path)
    if not res:
        raise HTTPException(status_code=404, detail=f"PDF not found at {storage_path}")
    return res.content if hasattr(res, "content") else res




