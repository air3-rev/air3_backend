"""API router for review generation operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import User
from app.schemas.review_generation import GenerateSectionRequest, GenerateSectionResponse
from app.services.data_extraction.fetch import _get_supabase
from app.services.review_generation.main import review_generation_service
from app.supabase_auth import get_current_user_from_supabase

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate-section-content", response_model=GenerateSectionResponse)
async def generate_section_content(
    request: GenerateSectionRequest,
    current_user: User = Depends(get_current_user_from_supabase),
):
    """
    Generate content for a section or subsection of the literature review.
    Requires authentication. User must own the review.
    """
    try:
        # Verify user owns the review
        sb = _get_supabase()
        review_check = sb.table("reviews").select("user_id").eq("id", request.review_id).single().execute()

        if not review_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review {request.review_id} not found",
            )

        if review_check.data["user_id"] != current_user.supabase_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to generate content for this review",
            )

        # Generate content
        response = await review_generation_service.generate_section_content(request)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating section content")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate section content: {str(e)}",
        )
