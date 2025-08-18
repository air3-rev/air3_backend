from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
import requests
from typing import Optional

from app.config import settings
from app.database import get_db, User
from app.schemas import SupabaseUser

security = HTTPBearer()


def verify_supabase_token(token: str) -> Optional[dict]:
    """
    Verify Supabase JWT token
    In a real implementation, you would verify against Supabase's public key
    """
    try:
        # This is a simplified example - in production you should:
        # 1. Fetch Supabase's public key from their JWKS endpoint
        # 2. Verify the token signature properly
        # 3. Check token expiration and other claims
        
        # For now, we'll decode without verification (NOT for production)
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except jwt.InvalidTokenError:
        return None


def get_current_user_from_supabase(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from Supabase token
    Creates user in local database if doesn't exist
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token
    payload = verify_supabase_token(credentials.credentials)
    if payload is None:
        raise credentials_exception
    
    supabase_id = payload.get("sub")
    email = payload.get("email")
    
    if not supabase_id or not email:
        raise credentials_exception
    
    # Check if user exists in local database
    user = db.query(User).filter(User.supabase_id == supabase_id).first()
    
    if not user:
        # Create user if doesn't exist
        user_metadata = payload.get("user_metadata", {})
        user = User(
            supabase_id=supabase_id,
            email=email,
            full_name=user_metadata.get("full_name"),
            avatar_url=user_metadata.get("avatar_url")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if token is provided, otherwise return None
    Useful for endpoints that work with or without authentication
    """
    if not credentials:
        return None
    
    try:
        payload = verify_supabase_token(credentials.credentials)
        if payload is None:
            return None
        
        supabase_id = payload.get("sub")
        if not supabase_id:
            return None
        
        return db.query(User).filter(User.supabase_id == supabase_id).first()
    except:
        return None