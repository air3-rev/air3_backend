import json
from typing import List, Optional
from app.schemas.lens_api_request import UserLensSearchInput
from app.schemas.search_response import EnrichedSearchResponse, PaginationMetadata
from app.schemas.lens_api_response import ScholarResponse
from app.services.lens_client import LensAPIClient, build_example_request, build_lens_request
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db, User
from app.schemas.user import UserResponse, UserUpdate, UserCreate
from app.supabase_auth import get_current_user_from_supabase, get_optional_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list", response_model=List[UserResponse])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all users (public endpoint)"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("list/{user_id}", response_model=UserResponse)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user_from_supabase)):
    """Get current user's profile"""
    return current_user


# @router.put("/me", response_model=UserResponse)
# async def update_current_user(
#     user_update: UserUpdate,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user_from_supabase)
# ):
#     """Update current user's profile"""
#     # Update user fields
#     update_data = user_update.dict(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(current_user, field, value)
    
#     db.commit()
#     db.refresh(current_user)
#     return current_user


# @router.post("/sync", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
# async def sync_user_from_supabase(
#     user_data: UserCreate,
#     db: Session = Depends(get_db)
# ):
#     """Sync user from Supabase (called by frontend after Supabase auth)"""
#     # Check if user already exists
#     existing_user = db.query(User).filter(User.supabase_id == user_data.supabase_id).first()
#     if existing_user:
#         return existing_user
    
#     # Create new user
#     db_user = User(
#         supabase_id=user_data.supabase_id,
#         email=user_data.email,
#         full_name=user_data.full_name,
#         avatar_url=user_data.avatar_url
#     )
    
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
    
#     return db_user
from typing import Any

@router.get("/test-search", response_model=None)
async def test_lens_search() -> Any:
    """
    Test route to call the Lens API with an example request.
    """
    try:
        logger.info("Starting test lens search...")
        client = LensAPIClient()
        logger.info("Created LensAPIClient")
        
        payload = build_example_request()
        logger.info("Final JSON payload:\n%s", json.dumps(payload.dict(by_alias=True), indent=2))

        logger.info(f"Payload dict: {payload.dict()}")
        
        api_response = client.search(payload)
        logger.info(f"Got {api_response.total} total results, returning {len(api_response.data)} items")
        
        # Parse the raw data into ScholarResponse objects for the test
        parsed_results = [ScholarResponse(**item) for item in api_response.data]
        return [r.dict() for r in parsed_results]
    except Exception as e:
        logger.exception("Lens API test search failed")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
    
@router.post("/search", response_model=EnrichedSearchResponse)
async def dynamic_lens_search(input: UserLensSearchInput) -> EnrichedSearchResponse:
    """
    Dynamic search route that returns enriched results with pagination metadata.
    """
    try:
        client = LensAPIClient()
        request_payload = build_lens_request(input)
        api_response = client.search(request_payload)
        
        # Parse the raw data into ScholarResponse objects
        parsed_articles = [ScholarResponse(**item) for item in api_response.data]
        
        # Create pagination metadata
        pagination = PaginationMetadata.create(
            total=api_response.total,
            offset=input.offset or 0,
            size=input.size or 10
        )
        
        # Build the enriched response
        return EnrichedSearchResponse(
            data=parsed_articles,
            pagination=pagination,
            max_score=api_response.max_score
        )
    except Exception as e:
        logger.exception("Dynamic lens search failed")
        raise HTTPException(status_code=500, detail=str(e))