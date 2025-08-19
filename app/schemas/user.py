from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# Supabase user info schema
class SupabaseUser(BaseModel):
    id: str
    email: str
    user_metadata: dict = {}

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


