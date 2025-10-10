"""
Service functions for journal operations.
"""
import json
import logging
from typing import List

import requests
from sqlalchemy.orm import Session

from app.database import Journal, get_journals_db, JournalsSessionLocal, JournalBase, journals_engine

# Configure logging
logger = logging.getLogger(__name__)

DATA_URL = "https://drive.google.com/uc?id=1ztxGWzF6V03V5vPAucPEUCu3IIEm0ucP"


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


def initialize_journals_db():
    """Initialize journals database by loading data from JSON file if not already loaded."""
    logger.info("Initializing journals database...")

    # Create tables (in case not created yet)
    JournalBase.metadata.create_all(bind=journals_engine)

    session = JournalsSessionLocal()

    try:
        # Check if already loaded
        count = session.query(Journal).count()
        if count > 0:
            logger.info(f"Journals database already initialized with {count} entries")
            return

        # Query existing (title, field) pairs to avoid duplicates
        existing_title_fields = {(row.title, row.field) for row in session.query(Journal.title, Journal.field).all()}

        # Load JSON data from remote URL
        response = requests.get(DATA_URL)
        response.raise_for_status()
        data = response.json()

        journals_to_insert = []
        skipped_duplicates = 0
        title_fields_to_insert = set()

        for field, journals in data.items():
            logger.info(f"Processing field: {field} ({len(journals)} journals)")

            for journal in journals:
                issns = journal['issn'].split(', ')
                rank = journal['rank']
                quartile = journal.get('quartile')
                title = journal['title']

                # Skip journals without quartile
                if not quartile:
                    continue

                # Skip if (title, field) already exists in DB or already being inserted in this batch
                if (title, field) in existing_title_fields or (title, field) in title_fields_to_insert:
                    skipped_duplicates += 1
                    continue

                title_fields_to_insert.add((title, field))

                # Create entry for each ISSN
                for issn in issns:
                    issn = issn.strip()
                    if issn:  # Skip empty ISSNs
                        journals_to_insert.append(Journal(
                            field=field,
                            issn=issn,
                            rank=rank,
                            quartile=quartile,
                            title=title
                        ))

        logger.info(f"Skipped {skipped_duplicates} duplicate journal titles")

        # Bulk insert
        logger.info(f"Inserting {len(journals_to_insert)} journal entries...")
        session.add_all(journals_to_insert)
        session.commit()
        logger.info("Successfully initialized journals database")

    except Exception as e:
        session.rollback()
        logger.error(f"Error initializing journals database: {e}")
        raise
    finally:
        session.close()