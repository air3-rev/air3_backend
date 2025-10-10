"""
Service functions for journal operations.
"""
from typing import List

from sqlalchemy.orm import Session

from app.database import Journal, get_journals_db


def get_issns(fields: List[str], quartiles: List[str]) -> List[str]:
    """
    Get list of ISSNs for journals matching any of the specified fields and quartiles.

    Args:
        fields: List of fields of study (e.g., ["Accounting", "Finance"]). If empty, matches all fields.
        quartiles: List of quartiles (e.g., ["Q1", "Q2"])

    Returns:
        List of ISSN strings
    """
    db: Session = next(get_journals_db())

    try:
        # Build query
        query = db.query(Journal.issn).filter(Journal.quartile.in_(quartiles))

        # Only filter by fields if fields are specified
        if fields:
            query = query.filter(Journal.field.in_(fields))

        journals = query.all()

        # Extract ISSNs from result tuples
        issns = [journal.issn for journal in journals]
        return issns

    finally:
        db.close()