"""
API router for journal operations.
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.services.journals import get_issns, get_related_categories

router = APIRouter()


@router.get("/journals", response_model=List[str])
async def get_journals_issns(
    fields: List[str] = Query(..., description="Fields of study (e.g., Accounting,Finance)"),
    quartiles: List[str] = Query(..., description="Quartiles (e.g., Q1,Q2)")
) -> List[str]:
    """
    Get list of ISSN numbers for journals in the specified fields and quartiles.

    Returns a list of ISSN strings matching the filters.
    """
    try:
        issns = get_issns(fields=fields, quartiles=quartiles)
        return issns
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving journals: {str(e)}")


@router.get("/categories/related")
async def get_related_categories_route(
    categories: List[str] = Query(..., description="Input categories to find relationships for"),
    limit: int = Query(10, description="Maximum number of related categories to return", ge=1, le=50)
):
    """
    Get top related categories based on category pairs data.

    Returns the top N most related categories (excluding input categories) based on
    co-occurrence frequency in the category pairs dataset.
    """
    try:
        if not categories:
            raise HTTPException(status_code=400, detail="At least one category must be provided")

        related = get_related_categories(categories=categories, limit=limit)
        return {"input_categories": categories, "related_categories": related}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving related categories: {str(e)}")