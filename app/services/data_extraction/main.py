import logging
from typing import Any, Dict

from app.services.data_extraction.fetch import fetch_relevant_chunks

logger = logging.getLogger(__name__)


def extract_data(label: str) -> Dict[Any, Any]:
    logger.info("Extraction data from label: %s", label)

    fetch_relevant_chunks(label)
    return {}
