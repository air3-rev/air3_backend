# app/routers/data_ingestion.py
"""Provides API endpoints to ingest data from external sources into the vector database."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.services.data_extraction.fetch import _get_supabase
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.services.data_extraction.main import extract_data as extract_data_service, extract_paper_data
from app.services.data_ingestion.main import download_pdf_from_storage, ingest_file as ingest_file_service, ingest_paper
from typing import Any, Dict, Optional

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
):
    ingest_file_service(file)




@router.get("/extract-paper-data")
async def extract_paper_data_route(
    extract_label: str,
    paper_id: str,
    k: int = 5,
) -> Dict[str, Any]:
    """
    Extract structured data for a label from a single paper.
    If the paper is not ingested yet, it will be ingested automatically.

    Args:
        extract_label: The label/question to extract (e.g., "Methods", "Results").
        paper_id: UUID of the paper (links to papers table).
        k: Number of top-k similar chunks to retrieve.

    Returns:
        Dict[str, Any] with summary, key_points, extracted_items, and sources.
    """
    try:
        # 1️⃣ Check if paper already has chunks in DB
        sb = _get_supabase()
        # existing = sb.table("paper_chunks").select("id").eq("paper_id", paper_id).limit(1).execute()
        existing = sb.table("paper_chunks").select("id").filter("metadata->>paper_id", "eq", paper_id).limit(1).execute()

        # logger.info("Existing", existing )
        logger.info(f'Existing: {existing}')

        if not existing.data:  
            logger.info("Paper %s not yet ingested, ingesting now...", paper_id)

            # 2️⃣ Get storage path from papers table
            paper_res = sb.table("papers").select("storage_path").eq("id", paper_id).single().execute()
            if not paper_res.data:
                raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found in papers table")

            storage_path = paper_res.data["storage_path"]
            logger.info(f'paper_res: {paper_res}')
            logger.info(f'storage_path: {storage_path}')
            
            
            # 3️⃣ Download file from Supabase storage
            pdf_bytes = download_pdf_from_storage(storage_path)
            logger.info(f'pdf_bytes: {pdf_bytes[0:150]}')

            # if not pdf_bytes:
            #     raise HTTPException(status_code=500, detail=f"Failed to download paper {paper_id} from storage")

            # # 4️⃣ Ingest into paper_chunks
            ingest_paper(pdf_bytes, paper_id=paper_id)

        # # 5️⃣ Run extraction now that chunks exist
        res = await run_in_threadpool(extract_paper_data, extract_label, k, paper_id)
        logger.info(f'Final Res: {res}')

        return res
        # return { "null": "null"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("extract-paper-data error")
        raise HTTPException(status_code=500, detail=str(e)) from e



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
