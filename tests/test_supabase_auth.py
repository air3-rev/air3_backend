"""Tests for JWT signature verification in supabase_auth.py (task C-1)."""

import time
import pytest
import jwt as pyjwt
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base, User
from app.supabase_auth import verify_supabase_token, get_current_user_from_supabase

# ── Fixtures ──────────────────────────────────────────────────────────────────

TEST_SECRET = "super-secret-jwt-key-for-testing-only"
WRONG_SECRET = "wrong-secret-that-attackers-would-use"

# In-memory DB for auth integration tests
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def auth_client():
    """Test client with DB override and a known JWT secret."""
    app.dependency_overrides[get_db] = override_get_db
    with patch("app.supabase_auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = TEST_SECRET
        yield TestClient(app)
    app.dependency_overrides.clear()


def make_token(secret: str, sub: str = "user-uuid-123", email: str = "test@example.com",
               exp_offset: int = 3600) -> str:
    """Build a signed HS256 JWT."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + exp_offset,
        "role": "authenticated",
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ── Unit tests: verify_supabase_token ────────────────────────────────────────

class TestVerifySupabaseToken:
    """Unit-level tests for the token verification function."""

    def test_valid_token_returns_payload(self):
        token = make_token(TEST_SECRET)
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = TEST_SECRET
            payload = verify_supabase_token(token)
        assert payload is not None
        assert payload["sub"] == "user-uuid-123"
        assert payload["email"] == "test@example.com"

    def test_forged_token_wrong_signature_returns_none(self):
        """Core security requirement: attacker-signed token must be rejected."""
        forged_token = make_token(WRONG_SECRET)
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = TEST_SECRET
            result = verify_supabase_token(forged_token)
        assert result is None, "Forged JWT with wrong signature must be rejected"

    def test_expired_token_returns_none(self):
        expired_token = make_token(TEST_SECRET, exp_offset=-1)
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = TEST_SECRET
            result = verify_supabase_token(expired_token)
        assert result is None

    def test_garbage_string_returns_none(self):
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = TEST_SECRET
            result = verify_supabase_token("not.a.jwt")
        assert result is None

    def test_missing_secret_raises_500(self):
        token = make_token(TEST_SECRET)
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = None
            with pytest.raises(HTTPException) as exc_info:
                verify_supabase_token(token)
        assert exc_info.value.status_code == 500
        assert "SUPABASE_JWT_SECRET" in exc_info.value.detail

    def test_empty_secret_raises_500(self):
        token = make_token(TEST_SECRET)
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = ""
            with pytest.raises(HTTPException) as exc_info:
                verify_supabase_token(token)
        assert exc_info.value.status_code == 500

    def test_tampered_payload_returns_none(self):
        """Altering the payload bytes invalidates the signature."""
        token = make_token(TEST_SECRET)
        header, payload_b64, sig = token.split(".")
        # Flip a character in the payload segment
        tampered_payload = payload_b64[:-1] + ("A" if payload_b64[-1] != "A" else "B")
        tampered_token = f"{header}.{tampered_payload}.{sig}"
        with patch("app.supabase_auth.settings") as s:
            s.supabase_jwt_secret = TEST_SECRET
            result = verify_supabase_token(tampered_token)
        assert result is None


# ── Integration tests via HTTP endpoint ──────────────────────────────────────

class TestAuthEndpointIntegration:
    """Test the /api/v1/users/me endpoint which requires a valid JWT."""

    def _client_with_secret(self, secret):
        app.dependency_overrides[get_db] = override_get_db
        mock_settings = MagicMock()
        mock_settings.supabase_jwt_secret = secret
        patcher = patch("app.supabase_auth.settings", mock_settings)
        patcher.start()
        client = TestClient(app, raise_server_exceptions=False)
        return client, patcher

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_valid_jwt_returns_200(self):
        token = make_token(TEST_SECRET)
        # Use a fresh file-backed SQLite so Base.metadata.create_all works
        import tempfile, os
        from app.database import Base as AppBase
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            tmp_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
            AppBase.metadata.create_all(bind=tmp_engine)
            TmpSession = sessionmaker(autocommit=False, autoflush=False, bind=tmp_engine)

            def tmp_db():
                db = TmpSession()
                try:
                    yield db
                finally:
                    db.close()

            app.dependency_overrides[get_db] = tmp_db
            mock_settings = MagicMock()
            mock_settings.supabase_jwt_secret = TEST_SECRET
            patcher = patch("app.supabase_auth.settings", mock_settings)
            patcher.start()
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            patcher.stop()
            app.dependency_overrides.clear()
            os.unlink(db_path)
        # 200 means auth passed (user was created/found)
        assert response.status_code == 200

    def test_forged_jwt_returns_401(self):
        """Attacker cannot access protected endpoints with a forged JWT."""
        forged_token = make_token(WRONG_SECRET)
        client, patcher = self._client_with_secret(TEST_SECRET)
        try:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {forged_token}"},
            )
        finally:
            patcher.stop()
            app.dependency_overrides.clear()
        assert response.status_code == 401

    def test_expired_jwt_returns_401(self):
        expired_token = make_token(TEST_SECRET, exp_offset=-60)
        client, patcher = self._client_with_secret(TEST_SECRET)
        try:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
        finally:
            patcher.stop()
            app.dependency_overrides.clear()
        assert response.status_code == 401

    def test_no_token_returns_403(self):
        client, patcher = self._client_with_secret(TEST_SECRET)
        try:
            response = client.get("/api/v1/users/me")
        finally:
            patcher.stop()
            app.dependency_overrides.clear()
        # HTTPBearer returns 403 when no credentials provided
        assert response.status_code in (401, 403)

    def test_malformed_token_returns_401(self):
        client, patcher = self._client_with_secret(TEST_SECRET)
        try:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer not.a.real.token"},
            )
        finally:
            patcher.stop()
            app.dependency_overrides.clear()
        assert response.status_code == 401

    def test_structurally_valid_but_unsigned_token_rejected(self):
        """
        PyJWT none-algorithm attack: a token with alg=none must be rejected.
        When algorithms=["HS256"] is enforced, alg=none tokens raise InvalidAlgorithmError.
        """
        # Build a "none" algorithm token manually
        import base64, json
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload_data = base64.urlsafe_b64encode(
            json.dumps({
                "sub": "attacker-uuid",
                "email": "attacker@evil.com",
                "exp": int(time.time()) + 3600,
            }).encode()
        ).rstrip(b"=").decode()
        unsigned_token = f"{header}.{payload_data}."

        client, patcher = self._client_with_secret(TEST_SECRET)
        try:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {unsigned_token}"},
            )
        finally:
            patcher.stop()
            app.dependency_overrides.clear()
        assert response.status_code == 401
