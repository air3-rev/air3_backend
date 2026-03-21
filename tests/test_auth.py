"""
T-1: Auth Tests

Tests for Supabase JWT validation and the get_current_user_from_supabase dependency.

Scenarios covered:
- Valid JWT -> 200 on a protected endpoint
- Expired JWT -> 401
- Wrong signature JWT -> 401
- Missing Authorization header -> 401
- First auth creates a local user in the database
- Subsequent auth returns the existing user (no duplicate creation)
"""

import time
import pytest
import jwt as pyjwt
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base, User
from app.supabase_auth import verify_supabase_token, get_current_user_from_supabase

# ---------------------------------------------------------------------------
# In-memory SQLite test database (StaticPool keeps single connection alive)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Shared JWT helpers
# ---------------------------------------------------------------------------

JWT_SECRET = "test-supabase-jwt-secret"

VALID_PAYLOAD = {
    "sub": "user-supabase-uuid-001",
    "email": "alice@example.com",
    "exp": int(time.time()) + 3600,
    "iat": int(time.time()),
    "user_metadata": {
        "full_name": "Alice Example",
        "avatar_url": "https://example.com/avatar.png",
    },
}


def _make_token(payload: dict, secret: str = JWT_SECRET, algorithm: str = "HS256") -> str:
    return pyjwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tables():
    """Wipe the users table before each test to avoid state leakage."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture
def auth_client():
    """Test client with in-memory DB and mocked settings JWT secret."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    with patch("app.supabase_auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = JWT_SECRET
        yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session():
    """Direct DB session for assertions."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Unit tests: verify_supabase_token
# ---------------------------------------------------------------------------

class TestVerifySupabaseToken:
    """Unit tests for the low-level token verification function."""

    def test_valid_token_returns_payload(self):
        token = _make_token(VALID_PAYLOAD)
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            result = verify_supabase_token(token)
        assert result is not None
        assert result["sub"] == VALID_PAYLOAD["sub"]
        assert result["email"] == VALID_PAYLOAD["email"]

    def test_expired_token_returns_none(self):
        expired_payload = {**VALID_PAYLOAD, "exp": int(time.time()) - 10}
        token = _make_token(expired_payload)
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            result = verify_supabase_token(token)
        assert result is None

    def test_wrong_signature_returns_none(self):
        token = _make_token(VALID_PAYLOAD, secret="wrong-secret")
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            result = verify_supabase_token(token)
        assert result is None

    def test_malformed_token_returns_none(self):
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            result = verify_supabase_token("not.a.valid.jwt")
        assert result is None

    def test_missing_secret_raises_500(self):
        from fastapi import HTTPException
        token = _make_token(VALID_PAYLOAD)
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = None
            with pytest.raises(HTTPException) as exc_info:
                verify_supabase_token(token)
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Integration tests: protected endpoint via TestClient
#
# We use GET /api/v1/users/me which is gated by get_current_user_from_supabase.
# ---------------------------------------------------------------------------

PROTECTED_ENDPOINT = "/api/v1/users/me"


class TestProtectedEndpointAuth:
    """Integration tests exercising the full auth dependency stack."""

    def test_valid_jwt_returns_200(self, auth_client):
        token = _make_token(VALID_PAYLOAD)
        response = auth_client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_expired_jwt_returns_401(self, auth_client):
        expired_payload = {**VALID_PAYLOAD, "exp": int(time.time()) - 10}
        token = _make_token(expired_payload)
        response = auth_client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_wrong_signature_returns_401(self, auth_client):
        token = _make_token(VALID_PAYLOAD, secret="totally-wrong-secret")
        response = auth_client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_missing_authorization_header_returns_401(self, auth_client):
        response = auth_client.get(PROTECTED_ENDPOINT)
        assert response.status_code == 403  # HTTPBearer returns 403 when header absent

    def test_malformed_bearer_token_returns_401(self, auth_client):
        response = auth_client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": "Bearer totally-not-a-jwt"},
        )
        assert response.status_code == 401

    def test_token_without_sub_returns_401(self, auth_client):
        payload_no_sub = {
            "email": "nosub@example.com",
            "exp": int(time.time()) + 3600,
        }
        token = _make_token(payload_no_sub)
        response = auth_client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_token_without_email_returns_401(self, auth_client):
        payload_no_email = {
            "sub": "user-no-email",
            "exp": int(time.time()) + 3600,
        }
        token = _make_token(payload_no_email)
        response = auth_client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Unit tests: get_current_user_from_supabase — user creation / retrieval
# ---------------------------------------------------------------------------

class TestGetCurrentUserFromSupabase:
    """Tests for local-user creation and retrieval logic."""

    def _make_credentials(self, payload: dict = None) -> MagicMock:
        payload = payload or VALID_PAYLOAD
        token = _make_token(payload)
        credentials = MagicMock()
        credentials.credentials = token
        return credentials

    def test_first_auth_creates_user_in_db(self, db_session):
        credentials = self._make_credentials()
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            user = get_current_user_from_supabase(credentials=credentials, db=db_session)

        assert user is not None
        assert user.supabase_id == VALID_PAYLOAD["sub"]
        assert user.email == VALID_PAYLOAD["email"]
        assert user.full_name == VALID_PAYLOAD["user_metadata"]["full_name"]
        assert user.avatar_url == VALID_PAYLOAD["user_metadata"]["avatar_url"]

        count = db_session.query(User).filter_by(supabase_id=VALID_PAYLOAD["sub"]).count()
        assert count == 1

    def test_subsequent_auth_returns_existing_user(self, db_session):
        """Calling the dependency twice must not create a duplicate row."""
        credentials = self._make_credentials()

        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            user_first = get_current_user_from_supabase(credentials=credentials, db=db_session)
            user_second = get_current_user_from_supabase(credentials=credentials, db=db_session)

        assert user_first.id == user_second.id
        count = db_session.query(User).filter_by(supabase_id=VALID_PAYLOAD["sub"]).count()
        assert count == 1

    def test_returns_correct_user_object_type(self, db_session):
        credentials = self._make_credentials()
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            user = get_current_user_from_supabase(credentials=credentials, db=db_session)
        assert isinstance(user, User)

    def test_user_without_metadata_fields_has_none_values(self, db_session):
        payload_no_meta = {
            "sub": "user-no-meta",
            "email": "nometa@example.com",
            "exp": int(time.time()) + 3600,
        }
        credentials = self._make_credentials(payload_no_meta)
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            user = get_current_user_from_supabase(credentials=credentials, db=db_session)
        assert user.full_name is None
        assert user.avatar_url is None

    def test_invalid_token_raises_401(self, db_session):
        from fastapi import HTTPException
        credentials = MagicMock()
        credentials.credentials = "invalid.token.here"
        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            with pytest.raises(HTTPException) as exc_info:
                get_current_user_from_supabase(credentials=credentials, db=db_session)
        assert exc_info.value.status_code == 401

    def test_two_different_users_are_both_created(self, db_session):
        payload_b = {
            "sub": "user-bob-uuid",
            "email": "bob@example.com",
            "exp": int(time.time()) + 3600,
        }
        creds_a = self._make_credentials(VALID_PAYLOAD)
        creds_b = self._make_credentials(payload_b)

        with patch("app.supabase_auth.settings") as mock_settings:
            mock_settings.supabase_jwt_secret = JWT_SECRET
            get_current_user_from_supabase(credentials=creds_a, db=db_session)
            get_current_user_from_supabase(credentials=creds_b, db=db_session)

        assert db_session.query(User).count() == 2
