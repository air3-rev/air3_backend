"""Provides API endpoints to ingest data from external sources into the vector database."""

import logging

# import tiktoken
from fastapi import UploadFile

from app.services.data_ingestion.process import chunk_document
from app.services.data_ingestion.read import parse_pdf_into_document, read_pdf_file
from app.services.data_ingestion.store import store_in_vector_db

logger = logging.getLogger(__name__)


def ingest_file(file: UploadFile):
    pdf_file = read_pdf_file(file)
    pdf_doc = parse_pdf_into_document(pdf_file)
    document_chunks = chunk_document(pdf_doc)
    logger.info("Document CHUNKS : ", document_chunks)
    logger.info("Baby, I'm-a want you !")
    store_in_vector_db(document_chunks)
