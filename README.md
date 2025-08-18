# Simple Python API

A modern, production-ready Python API built with FastAPI, designed for Supabase authentication integration, featuring CORS support, database integration, and comprehensive testing.

## Features

- **FastAPI Framework**: Modern, fast web framework for building APIs
- **Supabase Integration**: Seamless integration with Supabase authentication
- **CORS Support**: Cross-Origin Resource Sharing enabled for frontend integration
- **Database Integration**: SQLAlchemy ORM with support for SQLite, PostgreSQL, MySQL
- **User Management**: User synchronization and profile management with Supabase
- **Item Management**: Sample resource management with ownership controls
- **Security**: JWT token validation, input validation with Pydantic
- **Testing**: Comprehensive test suite with pytest
- **Docker Support**: Containerized deployment with Docker and docker-compose
- **Configuration**: Environment-based configuration management
- **Logging**: Structured logging with file and console output
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and middleware
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database models and connection
│   ├── schemas.py           # Pydantic models for request/response
│   ├── supabase_auth.py     # Supabase authentication utilities
│   └── routers/
│       ├── __init__.py
│       ├── users.py         # User management endpoints
│       └── items.py         # Item management endpoints
├── tests/
│   ├── __init__.py
│   └── test_main.py         # Test suite
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── run.py                  # Application runner
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Multi-service Docker setup
└── README.md               # This file
```

## Quick Start

### Local Development

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd simple-python-api
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**:
   ```bash
   python run.py
   ```

   Or using uvicorn directly:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the API**:
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc
   - Health check: http://localhost:8000/health

### Docker Deployment

1. **Build and run with Docker**:
   ```bash
   docker build -t simple-python-api .
   docker run -p 8000:8000 simple-python-api
   ```

2. **Or use docker-compose for full stack**:
   ```bash
   docker-compose up -d
   ```

   This will start:
   - API server on port 8000
   - PostgreSQL database on port 5432
   - Redis cache on port 6379
   - Nginx reverse proxy on port 80

## API Endpoints

### Users
- `GET /api/v1/users/` - List all users (public)
- `GET /api/v1/users/{user_id}` - Get user by ID
- `GET /api/v1/users/me` - Get current user profile (requires auth)
- `PUT /api/v1/users/me` - Update current user profile (requires auth)
- `POST /api/v1/users/sync` - Sync user from Supabase (called by frontend)

### Items
- `POST /api/v1/items/` - Create new item (requires auth)
- `GET /api/v1/items/` - Get items (user's own if authenticated, public if not)
- `GET /api/v1/items/all` - Get all public items
- `GET /api/v1/items/{item_id}` - Get item by ID
- `PUT /api/v1/items/{item_id}` - Update item (owner only, requires auth)
- `DELETE /api/v1/items/{item_id}` - Delete item (owner only, requires auth)
- `GET /api/v1/items/my-items` - Get current user's items (requires auth)
- `GET /api/v1/items/search?q={query}` - Search items

### System
- `GET /` - API information
- `GET /health` - Health check

## Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and modify as needed:

```env
# API Settings
APP_NAME=Simple Python API
DEBUG=False

# Database
DATABASE_URL=sqlite:///./app.db

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_main.py

# Run with verbose output
pytest -v
```

## Authentication Flow

1. **Register**: `POST /api/v1/auth/register` with user details
2. **Login**: `POST /api/v1/auth/login` with credentials
3. **Use Token**: Include `Authorization: Bearer <token>` header in requests
4. **Access Protected Routes**: All `/api/v1/users/` and `/api/v1/items/` routes require authentication

Example:
```bash
# Register
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "password123"}'

# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

# Use token
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <your-token-here>"
```

## Database

The API supports multiple database backends:

- **SQLite** (default): `sqlite:///./app.db`
- **PostgreSQL**: `postgresql://user:password@localhost/dbname`
- **MySQL**: `mysql://user:password@localhost/dbname`

Database tables are created automatically on startup.

## Security Features

- Password hashing with bcrypt
- JWT token authentication
- Token expiration
- Role-based access control (user/superuser)
- Input validation with Pydantic
- CORS configuration
- SQL injection protection via SQLAlchemy ORM

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in environment
2. Use a strong `SECRET_KEY`
3. Configure proper database (PostgreSQL recommended)
4. Set up reverse proxy (Nginx)
5. Enable HTTPS
6. Configure proper CORS origins
7. Set up monitoring and logging
8. Use environment variables for sensitive data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License.