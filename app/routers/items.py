from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, Item, User
from app.schemas import ItemResponse, ItemCreate, ItemUpdate
from app.supabase_auth import get_current_user_from_supabase, get_optional_user

router = APIRouter()


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_supabase)
):
    """Create a new item"""
    db_item = Item(
        title=item.title,
        description=item.description,
        owner_id=current_user.id
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return db_item


@router.get("/", response_model=List[ItemResponse])
async def read_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get items - user's own items if authenticated, all public items if not"""
    if current_user:
        # Return user's own items
        items = db.query(Item).filter(
            Item.owner_id == current_user.id
        ).offset(skip).limit(limit).all()
    else:
        # Return all active items for public access
        items = db.query(Item).filter(Item.is_active == True).offset(skip).limit(limit).all()
    return items


@router.get("/all", response_model=List[ItemResponse])
async def read_all_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all active items (public endpoint)"""
    items = db.query(Item).filter(Item.is_active == True).offset(skip).limit(limit).all()
    return items


@router.get("/{item_id}", response_model=ItemResponse)
async def read_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get a specific item by ID"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # If not authenticated, only show active items
    # If authenticated, show own items or active items from others
    if not current_user:
        if not item.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
    elif item.owner_id != current_user.id and not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    return item


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    item_update: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_supabase)
):
    """Update an item (owner only)"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # Users can only update their own items
    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Update item fields
    update_data = item_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_supabase)
):
    """Delete an item (owner only)"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # Users can only delete their own items
    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    db.delete(item)
    db.commit()
    return {"message": "Item deleted successfully"}


@router.get("/my-items", response_model=List[ItemResponse])
async def read_my_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_supabase)
):
    """Get current user's items"""
    items = db.query(Item).filter(
        Item.owner_id == current_user.id
    ).offset(skip).limit(limit).all()
    return items


@router.get("/search", response_model=List[ItemResponse])
async def search_items(
    q: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Search items by title or description"""
    base_query = db.query(Item).filter(
        (Item.title.contains(q)) | (Item.description.contains(q))
    )
    
    if current_user:
        # Show user's own items + active items from others
        items = base_query.filter(
            (Item.owner_id == current_user.id) | (Item.is_active == True)
        ).offset(skip).limit(limit).all()
    else:
        # Show only active items for public access
        items = base_query.filter(Item.is_active == True).offset(skip).limit(limit).all()
    
    return items