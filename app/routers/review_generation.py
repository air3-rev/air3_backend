# app/routers/review_generation.py
"""Provides API endpoints for literature review generation."""

import logging
from typing import Dict, Any, Optional

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

        # Build context from database by retrieving previously generated content
        request.previous_content = await _build_previous_content_context(sb, request.review_id, request.section_id, request.subsection_id)

        # Run the generation in a thread pool since it involves LLM calls
        response = await run_in_threadpool(review_generation_service.generate_section_content, request)

        # Store the generated content in the database
        await _store_generated_content(sb, request, response)

        logger.info(f"Successfully generated and stored content for section {request.section_id}")
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




async def _build_previous_content_context(
    sb,
    review_id: str,
    section_id: str,
    subsection_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build context of previously generated content from the database.

    Args:
        sb: Supabase client
        review_id: Review ID
        section_id: Current section ID (from structures table)
        subsection_id: Current subsection ID (if applicable)

    Returns:
        Dict containing previous sections and subsections content
    """
    context = {
        "sections": {},
        "subsections": {},
        "section_content": ""  # For subsection generation
    }

    try:
        # Get all generated sections for this review, ordered by creation time
        sections_result = sb.table('sections').select('*').eq('review_id', review_id).order('order_index').execute()
        generated_sections = sections_result.data or []

        # Create a mapping of section IDs to their content
        section_content_map = {}
        subsection_content_map = {}

        for section in generated_sections:
            if section.get('parent_section_id'):
                # This is a subsection
                parent_id = section['parent_section_id']
                if parent_id not in subsection_content_map:
                    subsection_content_map[parent_id] = {}
                subsection_content_map[parent_id][section['id']] = section.get('content', '')
            else:
                # This is a main section
                section_content_map[section['id']] = section.get('content', '')

        # For section generation: get content of previous sections
        context["sections"] = section_content_map

        # For subsection generation: get content of parent section and previous subsections
        if subsection_id:
            # Find the parent section content
            parent_sections = [s for s in generated_sections if s.get('parent_section_id') is None]
            current_parent = None

            # Find which parent section contains our subsection
            for parent in parent_sections:
                subsections_result = sb.table('sections').select('id').eq('parent_section_id', parent['id']).execute()
                subsection_ids = [s['id'] for s in subsections_result.data or []]
                if subsection_id in subsection_ids:
                    current_parent = parent
                    break

            if current_parent:
                context["section_content"] = current_parent.get('content', '')
                # Get previous subsections within the same parent
                parent_subsections = [s for s in generated_sections
                                    if s.get('parent_section_id') == current_parent['id']
                                    and s['id'] != subsection_id]
                # Sort by order_index to get sequential context
                parent_subsections.sort(key=lambda x: x.get('order_index', 0))
                context["subsections"] = {s['id']: s.get('content', '') for s in parent_subsections}

        logger.debug(f"Built context for section {section_id}, subsection {subsection_id}: {len(context['sections'])} sections, {len(context['subsections'])} subsections")

    except Exception as e:
        logger.warning(f"Error building previous content context: {e}")
        # Return empty context on error to avoid breaking generation

    return context


async def _store_generated_content(sb, request: GenerateSectionRequest, response: GenerateSectionResponse):
    """
    Store the generated content in the sections table.

    Args:
        sb: Supabase client
        request: Original generation request
        response: Generation response with content
    """
    try:
        # Get section details from structures table to get title and description
        section_result = sb.table('structures').select('title, description').eq('id', request.section_id).single().execute()
        section_data = section_result.data

        if not section_data:
            logger.warning(f"Could not find section {request.section_id} in structures table")
            return

        # Prepare data for insertion
        section_record = {
            'review_id': request.review_id,
            'title': section_data['title'],
            'description': section_data.get('description'),
            'content': response.content,
            'context': {
                'generated_at': response.generated_at.isoformat(),
                'metadata': response.metadata
            }
        }

        if request.subsection_id:
            # This is a subsection - find parent section
            subsection_result = sb.table('structures').select('title, description').eq('id', request.subsection_id).single().execute()
            subsection_data = subsection_result.data

            if subsection_data:
                section_record['title'] = subsection_data['title']
                section_record['description'] = subsection_data.get('description')

                # Find parent section ID in our sections table
                parent_result = sb.table('sections').select('id').eq('review_id', request.review_id).eq('title', section_data['title']).single().execute()
                if parent_result.data:
                    section_record['parent_section_id'] = parent_result.data['id']
        else:
            # This is a main section - determine order
            existing_sections = sb.table('sections').select('order_index').eq('review_id', request.review_id).is_('parent_section_id', None).execute()
            max_order = max([s.get('order_index', 0) for s in existing_sections.data or []]) if existing_sections.data else 0
            section_record['order_index'] = max_order + 1

        # Insert the record
        sb.table('sections').insert(section_record).execute()
        logger.debug(f"Stored generated content for section {request.section_id}")

    except Exception as e:
        logger.exception(f"Error storing generated content: {e}")
        # Don't raise exception - generation succeeded, storage failure shouldn't break the response


@router.get("/health")
async def review_generation_health() -> Dict[str, Any]:
    """Health check endpoint for the review generation service."""
    return {
        "status": "healthy",
        "service": "review_generation",
        "capabilities": ["section_generation", "subsection_generation", "context_aware"]
    }