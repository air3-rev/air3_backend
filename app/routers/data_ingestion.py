"""Provides API endpoints to ingest data from external sources into the vector database."""

import logging

# import tiktoken
from fastapi import APIRouter, File, UploadFile, status

from app.services.data_ingestion.main import ingest_file as ingest_file_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_file(
    file: UploadFile = File(..., description="A single PDF file"),
):
    ingest_file_service(file)


# @router.get("/extract-data")
# async def extract_data_from_file(
#     file: File,
#     extract_label: str,
# ):
#     """Extract data from a file based on user input, and return information."""
#     pass
