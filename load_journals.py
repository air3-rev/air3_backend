#!/usr/bin/env python3
"""
Script to load journal data from JSON into SQLite database.
"""
import json
import logging
from pathlib import Path
import requests
from sqlalchemy import create_engine, Column, Integer, String, Index
from sqlalchemy.orm import sessionmaker, declarative_base

# Define Journal model locally
JournalBase = declarative_base()

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "https://drive.google.com/uc?id=1ztxGWzF6V03V5vPAucPEUCu3IIEm0ucP"


def load_journals_data():
    """Load journal data from JSON file into database."""
    logger.info("Starting journal data loading...")

    # Create engine for journals db
    journals_engine = create_engine("sqlite:///./journals.db", connect_args={"check_same_thread": False})
    JournalsSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=journals_engine)

    # Create tables
    JournalBase.metadata.create_all(bind=journals_engine)
    logger.info("Created journals table")

    # Load JSON data
    response = requests.get(DATA_FILE)
    response.raise_for_status()
    data = response.json()

    session = JournalsSessionLocal()

    try:
        # Query existing titles to avoid duplicates
        existing_titles = {row[0] for row in session.query(Journal.title).all()}
        logger.info(f"Found {len(existing_titles)} existing journal titles")

        journals_to_insert = []
        skipped_duplicates = 0

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

                # Skip if title already exists
                if title in existing_titles:
                    skipped_duplicates += 1
                    continue

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
        logger.info("Successfully loaded journal data")

    except Exception as e:
        session.rollback()
        logger.error(f"Error loading data: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    load_journals_data()