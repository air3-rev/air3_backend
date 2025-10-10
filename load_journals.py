#!/usr/bin/env python3
"""
Script to load journal data from JSON into SQLite database.
"""
import json
import logging
from pathlib import Path

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
    title = Column(String(500), nullable=False)

    # Composite index for efficient querying by field and quartile
    __table_args__ = (
        Index('idx_field_quartile', 'field', 'quartile'),
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent / "app" / "data" / "category_journals.json"


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
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    session = JournalsSessionLocal()

    try:
        journals_to_insert = []

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