import logging
from typing import Any, Dict, List, Optional
from app.services.data_extraction.refine import refine_relevant_chunks
from app.services.data_ingestion.types import Chunk
from app.services.data_extraction.fetch import fetch_paper_chunks, fetch_relevant_chunks

logger = logging.getLogger(__name__)


def extract_data(label: str, k:int= 5, filter_doc_id: str = None) -> Dict[Any, Any]:
    logger.info("Extraction data from label: %s", label)

    relevant_chunks: List[Chunk] = fetch_relevant_chunks(label, 5)
    data = refine_relevant_chunks(relevant_chunks)
    logger.info(data)
    return data


def extract_paper_data(label: str, k: int = 5, paper_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract structured data for a single label from a specific paper.

    Args:
        label: The label to extract (e.g., 'Methods', 'Results').
        k: Number of top similar chunks to retrieve.
        paper_id: ID of the paper to extract from.

    Returns:
        Dict with keys: summary, key_points, extracted_items, sources.
    """
    logger.info("Extracting data for label '%s' from paper_id=%s", label, paper_id)

    # Fetch top-k relevant chunks for this paper
    relevant_chunks: List[Chunk] = fetch_paper_chunks(label, k=k, paper_id=paper_id)
    
    # Refine the chunks into a structured JSON document
    data = refine_relevant_chunks(relevant_chunks)
    logger.info("Extraction result: %s", data)
    return data