import json
from typing import List, Optional
from app.services.lens_client import LensAPIClient, build_example_request
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
        
        results = client.search(payload)
        logger.info(f"Got {len(results)} results")
        return [r.dict() for r in results]
    except Exception as e:
        logger.exception("Lens API test search failed")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))