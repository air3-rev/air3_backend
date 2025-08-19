from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# Base schemas
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


# User schemas (simplified for Supabase integration)
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    supabase_id: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: int
    supabase_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Item schemas
class ItemBase(BaseModel):
    title: str
    description: Optional[str] = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ItemResponse(ItemBase):
    id: int
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Supabase user info schema
class SupabaseUser(BaseModel):
    id: str
    email: str
    user_metadata: dict = {}


# Generic response schemas
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    message: str
    status_code: int