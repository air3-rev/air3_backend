import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_read_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_sync_user():
    """Test user sync from Supabase"""
    user_data = {
        "supabase_id": "test-supabase-id",
        "email": "test@example.com",
        "full_name": "Test User",
        "avatar_url": "https://example.com/avatar.jpg"
    }
    response = client.post("/api/v1/users/sync", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["supabase_id"] == user_data["supabase_id"]
    assert data["email"] == user_data["email"]
    assert "id" in data


def test_get_users():
    """Test getting all users"""
    response = client.get("/api/v1/users/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_all_items():
    """Test getting all public items"""
    response = client.get("/api/v1/items/all")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_search_items():
    """Test searching items"""
    response = client.get("/api/v1/items/search?q=test")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_cors_headers():
    """Test CORS headers are present"""
    response = client.get("/")
    assert "access-control-allow-origin" in response.headers


if __name__ == "__main__":
    pytest.main([__file__])