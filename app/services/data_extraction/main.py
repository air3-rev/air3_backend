import logging
from typing import Any, Dict, List
from app.services.data_extraction.refine import refine_relevant_chunks
from app.services.data_ingestion.types import Chunk
from app.services.data_extraction.fetch import fetch_relevant_chunks

logger = logging.getLogger(__name__)


def extract_data(label: str, k:int= 5, filter_doc_id: str = None) -> Dict[Any, Any]:
    logger.info("Extraction data from label: %s", label)

    relevant_chunks: List[Chunk] = fetch_relevant_chunks(label, 5)
    data = refine_relevant_chunks(relevant_chunks)
    logger.info(data)
    return data
