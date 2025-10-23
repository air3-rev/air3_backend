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