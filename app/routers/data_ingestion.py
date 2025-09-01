# app/routers/data_ingestion.py
"""Provides API endpoints to ingest data from external sources into the vector database."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.services.data_extraction.main import extract_data as extract_data_service
from app.services.data_ingestion.main import ingest_file as ingest_file_service

router = APIRouter()
logger = logging.getLogger(__name__)

# ----------------- Schemas (define BEFORE use) -----------------
class ExtractItemResponse(BaseModel):
    label: str
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class BatchExtractResponse(BaseModel):
    results: List[ExtractItemResponse]

class BatchExtractRequest(BaseModel):
    labels: List[str] = Field(..., min_length=1, max_length=50, description="List of labels to process")
    k: int = Field(5, ge=1, le=50, description="Top-k chunks per label")
    filter_doc_id: Optional[str] = Field(None, description="Optional doc filter")

# ----------------- Routes -----------------
@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_file(
    file: UploadFile = File(..., description="A single PDF file"),
) -> None:
    # Run sync work off the event loop
    await run_in_threadpool(ingest_file_service, file)

@router.get("/extract-data")
async def extract_data_from_file(
    extract_label: str,
    k: int = 5,
    filter_doc_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract data for a single label using vector search + refine."""
    try:
        return await run_in_threadpool(extract_data_service, extract_label, k, filter_doc_id)
    except Exception as e:
        logger.exception("extract-data error")
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/extract-data/batch", response_model=BatchExtractResponse)
async def extract_data_batch(payload: BatchExtractRequest) -> BatchExtractResponse:
    """Process multiple labels concurrently. Returns per-label results."""
    async def _run_one(label: str) -> ExtractItemResponse:
        try:
            data = await run_in_threadpool(extract_data_service, label, payload.k, payload.filter_doc_id)
            return ExtractItemResponse(label=label, ok=True, data=data)
        except Exception as e:
            logger.exception("Batch extract failed for label=%r", label)
            return ExtractItemResponse(label=label, ok=False, error=str(e))

    tasks = [asyncio.create_task(_run_one(lbl)) for lbl in payload.labels]
    results = await asyncio.gather(*tasks)
    return BatchExtractResponse(results=results)

@router.get("/extract-data/batch", response_model=BatchExtractResponse)
async def extract_data_batch_get(
    labels: List[str] = Query(..., description="Repeat parameter for multiple labels, e.g. ?labels=a&labels=b"),
    k: int = Query(5, ge=1, le=50),
    filter_doc_id: Optional[str] = Query(None),
) -> BatchExtractResponse:
    """GET variant for convenience (supports repeated ?labels=... parameters)."""
    if not labels:
        raise HTTPException(status_code=422, detail="At least one label is required")

    async def _run_one(label: str) -> ExtractItemResponse:
        try:
            data = await run_in_threadpool(extract_data_service, label, k, filter_doc_id)
            return ExtractItemResponse(label=label, ok=True, data=data)
        except Exception as e:
            logger.exception("Batch extract failed for label=%r", label)
            return ExtractItemResponse(label=label, ok=False, error=str(e))

    tasks = [asyncio.create_task(_run_one(lbl)) for lbl in labels]
    results = await asyncio.gather(*tasks)
    logger.info(results)
    return BatchExtractResponse(results=results)
