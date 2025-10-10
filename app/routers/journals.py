"""
API router for journal operations.
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.services.journals import get_issns

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