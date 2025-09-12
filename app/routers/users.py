import json
from typing import List, Optional
from app.schemas.lens_api_request import UserLensSearchInput
from app.schemas.search_response import EnrichedSearchResponse, PaginationMetadata
from app.schemas.lens_api_response import ScholarResponse
from app.services.lens_client import LensAPIClient, build_lens_request, build_lens_request_v2
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
   
    
@router.post("/search", response_model=EnrichedSearchResponse)
async def dynamic_lens_search(input: UserLensSearchInput) -> EnrichedSearchResponse:
    """
    Dynamic search route that returns enriched results with pagination metadata.
    """
    try:
        client = LensAPIClient()
        request_payload = build_lens_request_v2(input)
        api_response = client.search(request_payload)
        
        # Parse the raw data into ScholarResponse objects with error handling
        parsed_articles = []
        for item in api_response.data:
            try:
                # Fill in missing required fields with defaults
                if 'authors' in item and item['authors']:
                    for author in item['authors']:
                        if 'collective_name' not in author:
                            author['collective_name'] = None
                        if 'affiliations' not in author:
                            author['affiliations'] = []

                if 'source' in item and item['source']:
                    source = item['source']
                    if 'type' not in source:
                        source['type'] = None
                    if 'issn' not in source:
                        source['issn'] = []
                    if 'country' not in source:
                        source['country'] = None
                    if 'asjc_codes' not in source:
                        source['asjc_codes'] = None
                    if 'asjc_subjects' not in source:
                        source['asjc_subjects'] = None

                if 'references' in item and item['references']:
                    for ref in item['references']:
                        if 'text' not in ref:
                            ref['text'] = None

                parsed_articles.append(ScholarResponse(**item))
            except Exception as e:
                logger.warning(f"Failed to parse article: {e}, skipping item")
                continue
        
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