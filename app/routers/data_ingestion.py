# app/routers/data_ingestion.py
"""Provides API endpoints to ingest data from external sources into the vector database."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from app.schemas.schemas import DownloadPdfRequest
from app.services.data_extraction.fetch import _get_supabase
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, Response, Header
import httpx
import uuid
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.database import User
from app.services.data_extraction.main import extract_paper_data, extract_paper_data_with_full_text
from app.services.data_ingestion.read import read_paper_pdf_file
from app.services.data_ingestion.main import download_pdf_from_storage, ingest_paper
from app.supabase_auth import get_current_user_from_supabase
from typing import Any, Dict, Optional
from app.config import settings

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
    paper_id: Optional[str] = Field(None, description="Optional doc filter")

# ----------------- Routes -----------------

# ----DATA EXTRACTION----
@router.get("/extract-paper-data")
async def extract_paper_data_route(
    extract_label: str,
    paper_id: str,
    k: int = 5,
    current_user: User = Depends(get_current_user_from_supabase),
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
        existing = sb.table("paper_chunks").select("id").filter("metadata->>paper_id", "eq", paper_id).limit(1).execute()

        logger.debug(f'Existing chunks query result: {existing}')

        if not existing.data:  
            logger.info("Paper %s not yet ingested, ingesting now...", paper_id)

            # 2️⃣ Get storage path from papers table
            paper_res = sb.table("papers").select("storage_path").eq("id", paper_id).single().execute()
            if not paper_res.data:
                raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found in papers table")

            storage_path = paper_res.data["storage_path"]
            logger.debug(f'paper_res: {paper_res}')
            logger.debug(f'storage_path: {storage_path}')
            
            
            # 3️⃣ Download file from Supabase storage
            pdf_bytes = download_pdf_from_storage(storage_path)
            logger.debug(f'pdf_bytes preview: {pdf_bytes[0:150]}')

            # if not pdf_bytes:
            #     raise HTTPException(status_code=500, detail=f"Failed to download paper {paper_id} from storage")

            # # 4️⃣ Ingest into paper_chunks
            ingest_paper(pdf_bytes, paper_id=paper_id)

        # # 5️⃣ Run extraction now that chunks exist
        res = await run_in_threadpool(extract_paper_data, extract_label, k, paper_id)
        logger.debug(f'Final Res: {res}')

        return res

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("extract-paper-data error")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/batch-extract-paper-data")
async def batch_extract_paper_data_route(
    request: BatchExtractRequest,
    current_user: User = Depends(get_current_user_from_supabase),
) -> Dict[str, Any]:
    """
    Extract structured data for multiple labels from a single paper simultaneously.
    If the paper is not ingested yet, it will be ingested automatically.

    Args:
        request: BatchExtractRequest containing labels, k, and paper_id

    Returns:
        Dict[str, Any] with results for each label and metadata.
    """
    if not request.paper_id:
        raise HTTPException(status_code=400, detail="paper_id is required for batch extraction")
    
    try:
        # 1️⃣ Check if paper already has chunks in DB (same logic as original)
        sb = _get_supabase()
        existing = sb.table("paper_chunks").select("id").filter("metadata->>paper_id", "eq", request.paper_id).limit(1).execute()

        logger.debug(f'Existing chunks for paper {request.paper_id}: {existing}')

        # Always download PDF and extract full text for direct GPT-4 extraction
        logger.info("Downloading PDF for direct extraction...")

        # Get storage path from papers table
        paper_res = sb.table("papers").select("storage_path").eq("id", request.paper_id).single().execute()
        if not paper_res.data:
            raise HTTPException(status_code=404, detail=f"Paper {request.paper_id} not found in papers table")

        storage_path = paper_res.data["storage_path"]
        logger.debug(f'storage_path: {storage_path}')

        # Download file from Supabase storage
        pdf_bytes = download_pdf_from_storage(storage_path)
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Failed to download PDF")

        # Extract full text from PDF
        pdf_file = read_paper_pdf_file(pdf_bytes, filename=f"{request.paper_id}.pdf")
        full_text = pdf_file.content
        logger.debug(f'Extracted full text length: {len(full_text)}')

        # Extract data for all labels at once using full text
        try:
            all_results = await run_in_threadpool(extract_paper_data_with_full_text, request.labels, full_text)
            results = [(label, all_results.get(label, {"error": "Label not found in results"})) for label in request.labels]
        except Exception as e:
            logger.exception(f"Error extracting labels for paper {request.paper_id}")
            results = [(label, {"error": str(e)}) for label in request.labels]

        # 7️⃣ Process results and handle any exceptions
        final_results = {}
        successful_extractions = 0
        failed_extractions = 0

        for result in results:
            if isinstance(result, Exception):
                logger.exception("Task failed with exception: %s", result)
                failed_extractions += 1
            else:
                label, data = result
                final_results[label] = data
                if "error" in data:
                    failed_extractions += 1
                else:
                    successful_extractions += 1

        logger.info(f'Batch extraction completed for paper {request.paper_id}: {successful_extractions} successful, {failed_extractions} failed')

        return {
            "paper_id": request.paper_id,
            "results": final_results,
            "metadata": {
                "total_labels": len(request.labels),
                "successful_extractions": successful_extractions,
                "failed_extractions": failed_extractions,
                "extraction_method": "full_text_gpt4"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("batch-extract-paper-data error")
        raise HTTPException(status_code=500, detail=str(e)) from e



@router.post("/test-pdf-download")
async def test_pdf_download(
    url: str = Query(..., description="PDF URL to test"),
    current_user: User = Depends(get_current_user_from_supabase),
) -> Dict[str, Any]:
    """
    Test if a PDF URL is accessible and downloadable.
    Does not save to database - only verifies accessibility.

    Args:
        url: The PDF URL to test

    Returns:
        Dict with success status, content_type, size, and any error message
    """
    try:
        logger.info(f"Testing PDF download from: {url}")
        
        # Use httpx for async HTTP requests with proper headers
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*'
            }
        ) as client:
            response = await client.get(url)
            
            # Check response status
            if response.status_code != 200:
                logger.warning(f"Failed to download PDF: HTTP {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"HTTP error: {response.status_code}",
                    "url": url
                }
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            logger.debug(f"Content-Type: {content_type}")
            
            # Verify it's a PDF (some servers return application/octet-stream)
            is_pdf = (
                'application/pdf' in content_type or
                'application/octet-stream' in content_type or
                url.lower().endswith('.pdf')
            )
            
            if not is_pdf:
                logger.warning(f"URL does not return PDF content. Content-Type: {content_type}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "error": "URL does not return PDF content",
                    "url": url
                }
            
            # Get content size
            content_length = len(response.content)
            logger.debug(f"PDF size: {content_length} bytes ({content_length / 1024 / 1024:.2f} MB)")
            
            # Verify it's actually PDF content by checking magic bytes
            if len(response.content) >= 4:
                magic_bytes = response.content[:4]
                is_valid_pdf = magic_bytes == b'%PDF'
                
                if not is_valid_pdf:
                    logger.warning(f"Content does not have PDF magic bytes. First 4 bytes: {magic_bytes}")
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "content_type": content_type,
                        "size_bytes": content_length,
                        "error": "Content is not a valid PDF file",
                        "url": url
                    }
            
            # Success!
            logger.info(f"✅ Successfully accessed PDF from {url}")
            return {
                "success": True,
                "status_code": response.status_code,
                "content_type": content_type,
                "size_bytes": content_length,
                "size_mb": round(content_length / 1024 / 1024, 2),
                "url": url,
                "message": "PDF is accessible and valid"
            }
            
    except httpx.TimeoutException:
        logger.exception(f"Timeout accessing {url}")
        return {
            "success": False,
            "error": "Request timeout (>30s)",
            "url": url
        }
    except httpx.RequestError as e:
        logger.exception(f"Request error accessing {url}")
        return {
            "success": False,
            "error": f"Network error: {str(e)}",
            "url": url
        }
    except Exception as e:
        logger.exception(f"Unexpected error testing PDF download from {url}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "url": url
        }
        
        

@router.post("/download-and-store-pdf")
async def download_and_store_pdf(
    request: DownloadPdfRequest,
    current_user: User = Depends(get_current_user_from_supabase),
) -> Dict[str, Any]:
    """
    Download a PDF from a URL and store it in Supabase storage.
    Updates the papers table with the storage_path.

    Args:
        paper_id: UUID of the paper (links to papers table)
        pdf_url: URL of the PDF to download
        user_id: User ID for constructing storage path
        review_id: Review ID for constructing storage path
        authorization: Bearer token from session

    Returns:
        Dict with success status, storage_path, and file info
    """
    try:
        logger.info(f"Downloading PDF from {request.pdf_url} for paper {request.paper_id}")
        
        # 1️⃣ Download PDF from URL
        async with httpx.AsyncClient(
            timeout=60.0,  # Longer timeout for large files
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://misq.org/',  # Important! Shows you came from their site
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        ) as client:
            response = await client.get(request.pdf_url)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to download PDF: HTTP {response.status_code}"
                )
            
            pdf_bytes = response.content
            
            # Validate it's a PDF
            if len(pdf_bytes) < 4 or pdf_bytes[:4] != b'%PDF':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Downloaded content is not a valid PDF file"
                )
            
            # Check file size (20MB limit)
            if len(pdf_bytes) > 20 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF file size exceeds 20MB limit"
                )
            
            logger.info(f"Successfully downloaded PDF: {len(pdf_bytes)} bytes")
        
        # 2️⃣ Get Supabase client
        sb = _get_supabase()
        
        # 3️⃣ Generate file path (same pattern as frontend)
        file_path = f"{request.user_id}/{request.review_id}/{request.paper_id}.pdf"
        logger.debug(f"Storing PDF at path: {file_path}")
        
        # 4️⃣ Upload to Supabase storage
        try:
            upload_response = sb.storage.from_('papers_pdf').upload(
                path=file_path,
                file=pdf_bytes,
                file_options={
                    "content-type": "application/pdf",
                }
            )
            
            logger.debug(f"Upload response: {upload_response}")
            
        except Exception as storage_error:
            logger.exception("Error uploading to Supabase storage")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload PDF to storage: {str(storage_error)}"
            )
        
        # 5️⃣ Update papers table with storage_path
        try:
            update_response = sb.table('papers').update({
                'storage_path': file_path
            }).eq('id', request.paper_id).execute()
            
            if not update_response.data:
                logger.warning(f"No paper found with id {request.paper_id} to update")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Paper {request.paper_id} not found in database"
                )
            
            logger.info(f"Successfully updated paper {request.paper_id} with storage_path")
            
        except HTTPException:
            raise
        except Exception as db_error:
            logger.exception("Error updating papers table")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update paper record: {str(db_error)}"
            )
        
        # 6️⃣ Return success response
        return {
            "success": True,
            "paper_id": request.paper_id,
            "storage_path": file_path,
            "file_size_bytes": len(pdf_bytes),
            "file_size_mb": round(len(pdf_bytes) / 1024 / 1024, 2),
            "source_url": request.pdf_url,
            "message": "PDF successfully downloaded and stored"
        }
        
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.exception(f"Timeout downloading PDF from {request.pdf_url}")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Request timeout while downloading PDF (>60s)"
        )
    except httpx.RequestError as e:
        logger.exception(f"Network error downloading PDF from {request.pdf_url}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Network error while downloading PDF: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error in download-and-store-pdf")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )