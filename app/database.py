from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from app.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Journals database setup
journals_engine = create_engine(
    settings.journals_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.journals_database_url else {}
)

JournalsSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=journals_engine)

JournalBase = declarative_base()


# Dependency to get journals database session
def get_journals_db():
    db = JournalsSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Base model with common fields
class BaseModel(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# User model (simplified for Supabase integration)
class User(BaseModel):
    __tablename__ = "users"
    
    supabase_id = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    avatar_url = Column(String(255))


# Item model
class Item(BaseModel):
    __tablename__ = "items"

    title = Column(String(100), nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)


# Journal model for journals database
class Journal(JournalBase):
    __tablename__ = "journals"

    id = Column(Integer, primary_key=True, index=True)
    field = Column(String(255), nullable=False, index=True)
    issn = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=False)
    quartile = Column(String(10), nullable=False, index=True)
    title = Column(String(500), nullable=False, unique=True)

    # Composite index for efficient querying by field and quartile
    __table_args__ = (
        Index('idx_field_quartile', 'field', 'quartile'),
    )