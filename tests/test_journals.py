"""
Tests for journal operations.
"""
import pytest
from sqlalchemy.orm import Session

from app.database import Journal, get_journals_db
from app.services.journals import get_issns


class TestGetISSNs:
    """Test the get_issns function."""

    def test_get_issns_existing_data(self):
        """Test retrieving ISSNs for existing field and quartile."""
        issns = get_issns(["Accounting"], ["Q1"])
        assert isinstance(issns, list)
        # Assuming data is loaded, should return some ISSNs
        # In real test, would check specific values

    def test_get_issns_no_data(self):
        """Test retrieving ISSNs for non-existing field/quartile."""
        issns = get_issns(["NonExistentField"], ["Q1"])
        assert issns == []

    def test_get_issns_invalid_quartile(self):
        """Test with invalid quartile."""
        issns = get_issns(["Accounting"], ["Q5"])
        assert issns == []


class TestJournalAPI:
    """Test the journal API endpoints."""

    def test_get_journals_endpoint(self, client):
        """Test GET /api/v1/journals endpoint."""
        response = client.get("/api/v1/journals?fields=Accounting&quartiles=Q1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_journals_missing_params(self, client):
        """Test endpoint with missing parameters."""
        response = client.get("/api/v1/journals?fields=Accounting")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/v1/journals?quartiles=Q1")
        assert response.status_code == 422