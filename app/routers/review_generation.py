# app/routers/review_generation.py
"""Provides API endpoints for literature review generation."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from starlette.concurrency import run_in_threadpool

from app.schemas.review_generation import GenerateSectionRequest, GenerateSectionResponse
from app.services.review_generation.main import review_generation_service
from app.services.data_extraction.fetch import _get_supabase
from app.supabase_auth import get_current_user_from_supabase

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate-section-content", response_model=GenerateSectionResponse)
async def generate_section_content(
    request: GenerateSectionRequest,
    current_user = Depends(get_current_user_from_supabase)
) -> GenerateSectionResponse:
    """
    Generate content for a section or subsection of a literature review.

    This endpoint generates academic content for literature review sections by:
    1. Retrieving papers assigned to the specified section
    2. Gathering extracted data from those papers
    3. Using LangChain to generate coherent content considering context

    Args:
        request: GenerateSectionRequest containing review_id, section_id, and optional subsection_id
        current_user: Authenticated user information

    Returns:
        GenerateSectionResponse with generated content and metadata

    Raises:
        HTTPException: If generation fails, required data is missing, or user lacks permission
    """
    try:
        logger.info(f"Generating content for section {request.section_id} in review {request.review_id}")

        # Verify user owns the review
        sb = _get_supabase()
        review_check = sb.table('reviews').select('user_id').eq('id', request.review_id).single().execute()

        if not review_check.data or review_check.data['user_id'] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to generate content for this review"
            )

        # Build context from database instead of relying on frontend
        # Note: For now, we'll pass empty context since content storage isn't implemented yet
        # In the future, this would retrieve previously generated content from a database table
        request.previous_content = {
            "sections": {},
            "subsections": {},
            "section_content": ""
        }

        # Run the generation in a thread pool since it involves LLM calls
        response = await run_in_threadpool(review_generation_service.generate_section_content, request)

        logger.info(f"Successfully generated content for section {request.section_id}")
        return response

    except ValueError as e:
        logger.warning(f"Validation error during generation: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
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