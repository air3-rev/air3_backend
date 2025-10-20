# app/routers/review_generation.py
"""Provides API endpoints for literature review generation."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.schemas.review_generation import GenerateSectionRequest, GenerateSectionResponse
from app.services.review_generation.main import review_generation_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate-section-content", response_model=GenerateSectionResponse)
async def generate_section_content(request: GenerateSectionRequest) -> GenerateSectionResponse:
    """
    Generate content for a section or subsection of a literature review.

    This endpoint generates academic content for literature review sections by:
    1. Retrieving papers assigned to the specified section
    2. Gathering extracted data from those papers
    3. Using LangChain to generate coherent content considering context

    Args:
        request: GenerateSectionRequest containing review_id, section_id, and optional subsection_id

    Returns:
        GenerateSectionResponse with generated content and metadata

    Raises:
        HTTPException: If generation fails or required data is missing
    """
    try:
        logger.info(f"Generating content for section {request.section_id} in review {request.review_id}")

        # Run the generation in a thread pool since it involves LLM calls
        response = await run_in_threadpool(review_generation_service.generate_section_content, request)

        logger.info(f"Successfully generated content for section {request.section_id}")
        return response

    except ValueError as e:
        logger.warning(f"Validation error during generation: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Error generating section content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate section content. Please try again."
        ) from e


@router.get("/health")
async def review_generation_health() -> Dict[str, Any]:
    """Health check endpoint for the review generation service."""
    return {
        "status": "healthy",
        "service": "review_generation",
        "capabilities": ["section_generation", "subsection_generation", "context_aware"]
    }