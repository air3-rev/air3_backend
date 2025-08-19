from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# Base schemas
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True



# Generic response schemas
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    message: str
    status_code: int