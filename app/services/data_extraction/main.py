import logging
from typing import Any, Dict, List, Optional
from app.services.data_extraction.refine import refine_relevant_chunks
from app.services.data_ingestion.types import Chunk
from app.services.data_extraction.fetch import fetch_paper_chunks
from langchain_openai import ChatOpenAI
from app.config import settings
from app.services.data_extraction.prompts import get_multi_label_format_instructions

logger = logging.getLogger(__name__)


def extract_paper_data_with_full_text(labels: List[str], full_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract structured data for multiple labels from the full text of a paper using GPT-4.
    Processes all labels together to avoid overlap between different label extractions.

    Args:
        labels: List of label prompts to extract (e.g., ['Methods', 'Results']).
        full_text: The full text content of the paper.

    Returns:
        Dict mapping each label to its extraction results with keys: summary, key_points, extracted_items, sources.
    """
    logger.info("Extracting data for %d labels using full text (length: %d)", len(labels), len(full_text))

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.full_text_extraction_model, 
        temperature=0.1,  # Lower temperature for more consistent, factual extraction
        max_tokens=12000,
        timeout=600,
    ).bind(response_format={"type": "json_object"})

    labels_text = "\n".join([f"- {label}" for label in labels])
    multi_label_instructions = get_multi_label_format_instructions(labels)

    prompt = f"""You are a precise data extractor for academic papers. Extract information for each label below.

        CRITICAL RULES:
        1. If a label is NOT APPLICABLE/MENTIONED, return ONLY:
        {{"summary": "N/A", "key_points": [], "extracted_items": [], "sources": []}}
        
        2. If applicable, follow these formatting standards:
        - Summary: Direct, descriptive answer. NO introductory filler. 
        - Clarity Requirement: Define all acronyms/codes upon first use.
            * POOR: "SA, SW, AB"
            * CLEAR: "Slugging Average (SA), Strikeouts (SW), At Bats (AB)"
        - Key Points: Use "Category: Finding" format. Max 25 words per point.
            * EXAMPLE: "Independent Variables: 9 performance metrics (SA, SW, etc.)"
            * EXAMPLE: "Sample Size: 500 MLB players (2010-2020)"
        - Punctuation: Use semicolons to separate distinct groups; commas for items within groups.

        3. Constraints:
        - Do NOT use full sentences unless a relationship is too complex for a fragment.
        - Do NOT repeat the label name in the summary.
        - Ensure the "Summary" provides enough context to be understood without reading the full paper.

        Labels to extract:
        {labels_text}

        Response format for EACH label:
        - summary: Contextualized direct answer (or "N/A")
        - key_points: Array of short descriptive fragments (or [])
        - extracted_items: Structured data/mappings if applicable (or [])
        - sources: Page/section references (or [])

        {multi_label_instructions}

        Paper text:
        {full_text[:50000]}
    """

    try:
        response = llm.invoke(prompt)
        result = response.content
        logger.info("GPT-4 extraction result: %s", result[:500])

        import json
        data = json.loads(result)

        results = {}
        for label in labels:
            label_key = label.split(':')[0].strip()
            
            # Try to get data from response
            label_data = data.get(label_key) or data.get(label) or {}
            
            summary = label_data.get("summary", "N/A")
            key_points = label_data.get("key_points", [])
            extracted_items = label_data.get("extracted_items", [])
            sources = label_data.get("sources", [])
            
            # Normalize N/A responses - if summary is N/A, ensure other fields are empty
            if summary in ["N/A", "Not applicable", "Not mentioned", "Not reported", ""]:
                summary = "N/A"
                key_points = []
                extracted_items = []
                sources = []
            
            results[label] = {
                "summary": summary,
                "key_points": key_points,
                "extracted_items": extracted_items,
                "sources": sources
            }

        return results
        
    except Exception as e:
        logger.exception("Error in GPT-4 extraction")
        return {label: {
            "summary": "Error extracting data",
            "key_points": [],
            "extracted_items": [],
            "sources": []
        } for label in labels
        }

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