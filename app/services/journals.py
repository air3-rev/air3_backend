"""
Service functions for journal operations.
"""
import json
import logging
from typing import List
from urllib.parse import unquote

import requests
from sqlalchemy.orm import Session

from app.database import Journal, Category_Pairs, get_journals_db, JournalsSessionLocal, JournalBase, journals_engine

# Configure logging
logger = logging.getLogger(__name__)

DATA_URL = "https://drive.google.com/uc?id=1ztxGWzF6V03V5vPAucPEUCu3IIEm0ucP"
CATEGORY_PAIRS_URL = "https://drive.google.com/uc?id=1SfpTAFxbzbTtrBvDkyg2ZubUOPG88Knp"


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

        # Extract ISSNs from result tuples, filter out None and empty values
        issns = [journal.issn for journal in journals if journal.issn and journal.issn.strip()]
        return issns

    finally:
        db.close()


def get_related_categories(categories: List[str], limit: int = 10) -> List[dict]:
    """
    Get top related categories based on category pairs data.

    Args:
        categories: List of input categories to find relationships for
        limit: Maximum number of related categories to return

    Returns:
        List of dicts with 'category' and 'total_frequency' keys, sorted by frequency desc
    """
    db: Session = next(get_journals_db())

    try:
        from collections import defaultdict

        # URL decode the input categories to handle encoded spaces
        decoded_categories = [unquote(cat) for cat in categories]

        # Convert input categories to set for faster lookup
        input_categories = set(decoded_categories)

        # Query all pairs where either category_1 or category_2 matches input categories
        pairs = db.query(Category_Pairs).filter(
            (Category_Pairs.category_1.in_(decoded_categories)) |
            (Category_Pairs.category_2.in_(decoded_categories))
        ).all()

        # Aggregate frequencies for related categories
        related_freq = defaultdict(int)

        for pair in pairs:
            # Determine which category is the related one (not in input)
            if pair.category_1 in input_categories and pair.category_2 not in input_categories:
                related_freq[pair.category_2] += pair.frequency
            elif pair.category_2 in input_categories and pair.category_1 not in input_categories:
                related_freq[pair.category_1] += pair.frequency
            # If both are in input categories, skip (no self-relationships)

        # Sort by frequency and take top limit
        sorted_related = sorted(
            [{"category": cat, "total_frequency": freq} for cat, freq in related_freq.items()],
            key=lambda x: x["total_frequency"],
            reverse=True
        )[:limit]

        return sorted_related

    finally:
        db.close()


def load_journals_db():
    """Load journals and category pairs data into the database."""
    logger.info("Loading journals database...")

    # Create tables (in case not created yet)
    JournalBase.metadata.create_all(bind=journals_engine)

    session = JournalsSessionLocal()

    try:
        # Load journals data
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

        # Bulk insert journals
        logger.info(f"Inserting {len(journals_to_insert)} journal entries...")
        session.add_all(journals_to_insert)
        session.commit()
        logger.info("Successfully loaded journals data")

        # Load category pairs data
        # Query existing (category_1, category_2) pairs to avoid duplicates
        existing_pairs = {(row.category_1, row.category_2) for row in session.query(Category_Pairs.category_1, Category_Pairs.category_2).all()}

        # Load category pairs JSON data from remote URL
        response = requests.get(CATEGORY_PAIRS_URL)
        response.raise_for_status()
        pairs_data = response.json()

        pairs_to_insert = []
        skipped_pair_duplicates = 0
        pairs_to_insert_set = set()

        for pair in pairs_data:
            category_1 = pair['Category_1']
            category_2 = pair['Category_2']
            frequency = pair['Frequency']

            # Skip if (category_1, category_2) already exists in DB or already being inserted
            pair_key = (category_1, category_2)
            if pair_key in existing_pairs or pair_key in pairs_to_insert_set:
                skipped_pair_duplicates += 1
                continue

            pairs_to_insert_set.add(pair_key)
            pairs_to_insert.append(Category_Pairs(
                category_1=category_1,
                category_2=category_2,
                frequency=frequency
            ))

        logger.info(f"Skipped {skipped_pair_duplicates} duplicate category pairs")

        # Bulk insert category pairs
        logger.info(f"Inserting {len(pairs_to_insert)} category pair entries...")
        session.add_all(pairs_to_insert)
        session.commit()
        logger.info("Successfully loaded category pairs data")

        logger.info("Successfully loaded journals database")

    except Exception as e:
        session.rollback()
        logger.error(f"Error loading journals database: {e}")
        raise
    finally:
        session.close()


def empty_journals_db():
    """Empty the journals database by deleting all data from journals and category_pairs tables."""
    logger.info("Emptying journals database...")

    session = JournalsSessionLocal()

    try:
        # Delete all category pairs
        pairs_deleted = session.query(Category_Pairs).delete()
        logger.info(f"Deleted {pairs_deleted} category pairs")

        # Delete all journals
        journals_deleted = session.query(Journal).delete()
        logger.info(f"Deleted {journals_deleted} journals")

        session.commit()
        logger.info("Successfully emptied journals database")

    except Exception as e:
        session.rollback()
        logger.error(f"Error emptying journals database: {e}")
        raise
    finally:
        session.close()


def search_journals_by_name(search_term: str, limit: int = 10) -> List[str]:
    """
    Search journals by title/name.

    Args:
        search_term: The search term to match against journal titles
        limit: Maximum number of results to return

    Returns:
        List of journal titles matching the search term
    """
    db: Session = next(get_journals_db())

    try:
        # Search for journals where title contains the search term (case-insensitive)
        journals = db.query(Journal.title).filter(
            Journal.title.ilike(f'%{search_term}%')
        ).distinct().limit(limit).all()

        # Extract titles from result tuples
        titles = [journal.title for journal in journals]
        return titles

    finally:
        db.close()


def get_issns_by_titles(titles: List[str]) -> List[str]:
    """
    Get ISSN numbers for the given journal titles.

    Args:
        titles: List of journal titles

    Returns:
        List of ISSN strings
    """
    db: Session = next(get_journals_db())

    try:
        # Query ISSNs for the given titles
        journals = db.query(Journal.issn).filter(Journal.title.in_(titles)).all()

        # Extract ISSNs from result tuples, filter out None and empty values
        issns = [journal.issn for journal in journals if journal.issn and journal.issn.strip()]
        return issns

    finally:
        db.close()


def get_journals_by_ranking(ranking: str) -> List[str]:
    """
    Get journal titles for the given ranking.

    Args:
        ranking: Ranking type ("FT50", "HEC", or "IS")

    Returns:
        List of journal title strings
    """
    from app.routers.papers import FT50_ISSN_NUMBERS, HEC_Accounting_ISSN_NUMBERS, IS_Information_Systems_ISSN_NUMBERS

    if ranking == "FT50":
        issns = FT50_ISSN_NUMBERS
    elif ranking == "HEC":
        issns = HEC_Accounting_ISSN_NUMBERS
    elif ranking == "IS":
        issns = IS_Information_Systems_ISSN_NUMBERS
    else:
        return []

    db: Session = next(get_journals_db())

    try:
        # Query titles for the given ISSNs
        journals = db.query(Journal.title).filter(Journal.issn.in_(issns)).distinct().all()

        # Extract titles from result tuples
        titles = [journal.title for journal in journals]

        # If no titles found in database, return some sample journal names for the ranking
        # This ensures the UI shows something even if database is not populated
        if not titles:
            if ranking == "FT50":
                titles = [
                    "Academy of Management Journal", "Academy of Management Review", "Administrative Science Quarterly",
                    "Journal of Management", "Organization Science", "Strategic Management Journal",
                    "Journal of Marketing", "Marketing Science", "Journal of Consumer Research",
                    "Journal of Finance", "Journal of Financial Economics", "The Accounting Review"
                ][:10]  # Limit to 10 for UI
            elif ranking == "HEC":
                titles = [
                    "Academy of Management Journal", "Academy of Management Review", "Administrative Science Quarterly",
                    "Journal of Management", "Organization Science", "Strategic Management Journal",
                    "Journal of Marketing", "Marketing Science", "Journal of Consumer Research",
                    "The Accounting Review", "Journal of Accounting Research", "Contemporary Accounting Research"
                ][:10]  # Limit to 10 for UI
            elif ranking == "IS":
                titles = [
                    "MIS Quarterly", "Information Systems Research", "Journal of Management Information Systems",
                    "Journal of Strategic Information Systems", "European Journal of Information Systems",
                    "Information & Management", "Journal of the Association for Information Systems",
                    "Information Systems Journal"
                ]

        return titles

    finally:
        db.close()


def initialize_journals_db():
    """Initialize journals database by loading data from JSON file if not already loaded."""
    logger.info("Initializing journals database...")

    # Create tables (in case not created yet)
    JournalBase.metadata.create_all(bind=journals_engine)

    session = JournalsSessionLocal()

    try:
        # Check if journals already loaded
        journals_count = session.query(Journal).count()
        journals_loaded = journals_count > 0
        if journals_loaded:
            logger.info(f"Journals database already initialized with {journals_count} entries")
        else:
            logger.info("Journals database is empty, will load journals data")
            load_journals_db()

        # Load category pairs data
        logger.info("Loading category pairs data...")

        # Check if category pairs already loaded
        pairs_count = session.query(Category_Pairs).count()
        if pairs_count > 0:
            logger.info(f"Category pairs already loaded with {pairs_count} entries")
        else:
            # Load category pairs
            # Query existing (category_1, category_2) pairs to avoid duplicates
            existing_pairs = {(row.category_1, row.category_2) for row in session.query(Category_Pairs.category_1, Category_Pairs.category_2).all()}

            # Load category pairs JSON data from remote URL
            response = requests.get(CATEGORY_PAIRS_URL)
            response.raise_for_status()
            pairs_data = response.json()

            pairs_to_insert = []
            skipped_pair_duplicates = 0
            pairs_to_insert_set = set()

            for pair in pairs_data:
                category_1 = pair['Category_1']
                category_2 = pair['Category_2']
                frequency = pair['Frequency']

                # Skip if (category_1, category_2) already exists in DB or already being inserted
                pair_key = (category_1, category_2)
                if pair_key in existing_pairs or pair_key in pairs_to_insert_set:
                    skipped_pair_duplicates += 1
                    continue

                pairs_to_insert_set.add(pair_key)
                pairs_to_insert.append(Category_Pairs(
                    category_1=category_1,
                    category_2=category_2,
                    frequency=frequency
                ))

            logger.info(f"Skipped {skipped_pair_duplicates} duplicate category pairs")

            # Bulk insert category pairs
            logger.info(f"Inserting {len(pairs_to_insert)} category pair entries...")
            session.add_all(pairs_to_insert)
            session.commit()
            logger.info("Successfully loaded category pairs data")

        logger.info("Successfully initialized journals database")

    except Exception as e:
        session.rollback()
        logger.error(f"Error initializing journals database: {e}")
        raise
    finally:
        session.close()