"""
API router for journal operations.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import User
from app.services.journals import get_issns, get_related_categories, load_journals_db, empty_journals_db, search_journals_by_name, get_issns_by_titles, get_journals_by_ranking
from app.supabase_auth import get_current_user_from_supabase

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


@router.post("/load")
async def load_journals_database(
    current_user: User = Depends(get_current_user_from_supabase),
):
    """
    Load journals and category pairs data into the database.
    This will load data from remote URLs and insert into the database.
    Existing data will not be duplicated. Requires authentication.
    """
    try:
        load_journals_db()
        return {"message": "Journals database loaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading journals database: {str(e)}")


@router.post("/empty")
async def empty_journals_database(
    current_user: User = Depends(get_current_user_from_supabase),
):
    """
    Empty the journals database by deleting all journals and category pairs data.
    Requires authentication.
    """
    try:
        empty_journals_db()
        return {"message": "Journals database emptied successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error emptying journals database: {str(e)}")


@router.get("/search", response_model=List[str])
async def search_journals(
    q: str = Query(..., description="Search query for journal names"),
    limit: int = Query(10, description="Maximum number of results to return", ge=1, le=50)
) -> List[str]:
    """
    Search for journals by name/title.

    Returns a list of journal titles that match the search query.
    """
    try:
        if not q or len(q.strip()) < 2:
            raise HTTPException(status_code=400, detail="Search query must be at least 2 characters long")

        journals = search_journals_by_name(q.strip(), limit=limit)
        return journals
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching journals: {str(e)}")


@router.get("/issns", response_model=List[str])
async def get_journals_issns_by_titles(
    titles: str = Query(..., description="Comma-separated journal titles to get ISSNs for")
) -> List[str]:
    """
    Get ISSN numbers for the specified journal titles.

    Returns a list of ISSN strings for the given journal titles.
    """
    try:
        # Split comma-separated titles and clean up whitespace
        title_list = [title.strip() for title in titles.split(',') if title.strip()]

        if not title_list:
            raise HTTPException(status_code=400, detail="At least one journal title must be provided")

        issns = get_issns_by_titles(title_list)
        return issns
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving ISSNs: {str(e)}")


@router.get("/ranking/{ranking}", response_model=List[str])
async def get_journals_for_ranking(ranking: str) -> List[str]:
    """
    Get journal titles for the specified ranking.

    Returns a list of journal title strings for the given ranking.
    """
    try:
        if ranking not in ["FT50", "HEC", "IS"]:
            raise HTTPException(status_code=400, detail="Ranking must be 'FT50', 'HEC', or 'IS'")

        journals = get_journals_by_ranking(ranking)
        return journals
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving journals for ranking: {str(e)}")