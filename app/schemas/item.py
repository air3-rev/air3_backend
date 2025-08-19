from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


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