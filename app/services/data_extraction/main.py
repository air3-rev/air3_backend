import logging
from typing import Any, Dict, List, Optional
from app.services.data_extraction.refine import refine_relevant_chunks
from app.services.data_ingestion.types import Chunk
from app.services.data_extraction.fetch import fetch_paper_chunks, fetch_relevant_chunks
from langchain_openai import ChatOpenAI
from app.config import settings
from app.services.data_extraction.prompts import FORMAT_INSTRUCTIONS, get_multi_label_format_instructions

logger = logging.getLogger(__name__)


def extract_data(label: str, k:int= 5, filter_doc_id: str = None) -> Dict[Any, Any]:
    logger.info("Extraction data from label: %s", label)

    relevant_chunks: List[Chunk] = fetch_relevant_chunks(label, 5)
    data = refine_relevant_chunks(relevant_chunks)
    logger.info(data)
    return data


# def extract_paper_data_with_full_text(labels: List[str], full_text: str) -> Dict[str, Dict[str, Any]]:
#     """
#     Extract structured data for multiple labels from the full text of a paper using GPT-4.
#     Processes all labels together to avoid overlap between different label extractions.

#     Args:
#         labels: List of label prompts to extract (e.g., ['Methods', 'Results']).
#         full_text: The full text content of the paper.

#     Returns:
#         Dict mapping each label to its extraction results with keys: summary, key_points, extracted_items, sources.
#     """
#     logger.info("Extracting data for %d labels using full text (length: %d)", len(labels), len(full_text))

#     # Use GPT-4 for direct extraction from full text
#     llm = ChatOpenAI(
#         api_key=settings.openai_api_key,
#         model="gpt-4.1", 
#         temperature=0.3,
#         max_tokens=12000,  # Increased for multiple labels
#         timeout=600,
#     ).bind(response_format={"type": "json_object"})

#     # Format labels for the prompt
#     labels_text = "\n".join([f"- {label}" for label in labels])

#     # Get format instructions for multiple labels
#     multi_label_instructions = get_multi_label_format_instructions(labels)

#     prompt = f"""You are a precise data extractor focused on extracting specific information from academic papers.

# You must extract information for ALL of the following labels. Be careful to assign information to the CORRECT label only - do not put information in the wrong category.

# Labels to extract:
# {labels_text}

# For EACH label, provide:
# - Summary: Single paragraph, maximum 200 words, summarizing ONLY the information relevant to this specific label
# - Key points: 3-7 most important items ONLY related to this label, each under 30 words
# - Extracted items: Structured data fields ONLY relevant to this label (if applicable)
# - Sources: Reference to page numbers or sections where information for this label was found

# IMPORTANT:
# - Do NOT include information from one label in another label's results
# - If a label has no relevant information in the paper, provide empty arrays but still include the label
# - Be precise about which information belongs to which label
# - Cross-reference the labels to ensure no overlap

# {multi_label_instructions}

# Full paper text:
# {full_text[:50000]}  # Limit to first 50k chars to avoid token limits
# """

#     try:
#         response = llm.invoke(prompt)
#         result = response.content
#         logger.info("GPT-4 extraction result: %s", result[:500])

#         # Parse JSON
#         import json
#         data = json.loads(result)

#         # Ensure all labels are present in the result
#         results = {}
#         for label in labels:
#             label_key = label.split(':')[0].strip()  # Use the label name as key
#             if label_key in data:
#                 results[label] = {
#                     "summary": data[label_key].get("summary", ""),
#                     "key_points": data[label_key].get("key_points", []),
#                     "extracted_items": data[label_key].get("extracted_items", []),
#                     "sources": data[label_key].get("sources", [])
#                 }
#             else:
#                 # Fallback: try to find by full label text
#                 results[label] = {
#                     "summary": data.get(label, {}).get("summary", ""),
#                     "key_points": data.get(label, {}).get("key_points", []),
#                     "extracted_items": data.get(label, {}).get("extracted_items", []),
#                     "sources": data.get(label, {}).get("sources", [])
#                 }

#         return results
#     except Exception as e:
#         logger.exception("Error in GPT-4 extraction")
#         # Return empty results for all labels on error
#         return {label: {
#             "summary": "Error extracting data",
#             "key_points": [],
#             "extracted_items": [],
#             "sources": []
#         } for label in labels}


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
        model="gpt-4.1", 
        temperature=0.1,  # Lower temperature for more consistent, factual extraction
        max_tokens=12000,
        timeout=600,
    ).bind(response_format={"type": "json_object"})

    labels_text = "\n".join([f"- {label}" for label in labels])
    multi_label_instructions = get_multi_label_format_instructions(labels)

    prompt = f"""You are a precise data extractor for academic papers. Extract information for each label below.

CRITICAL RULES:
1. If a label is NOT APPLICABLE or NOT MENTIONED in the paper, return ONLY:
   {{"summary": "N/A", "key_points": [], "extracted_items": [], "sources": []}}
   
2. If a label IS applicable, be EXTREMELY CONCISE:
   - Summary: Direct answer only. No filler phrases like "This paper discusses..." or "The authors examine..."
     * BAD: "The study uses a sample of 2,000 transfers from the top five European leagues between 2012-2021."
     * GOOD: "2,000 transfers; top 5 European leagues; 2012-2021"
   - Key points: Short fragments, not full sentences. Max 10 words each.
     * BAD: "The authors found that age has an inverted U-shaped relationship with player value."
     * GOOD: "Age effect: inverted U-shape"
   - Use semicolons, commas, and lists instead of prose
   - Only use full sentences when nuance is absolutely required

3. Do NOT:
   - Repeat information across labels
   - Add generic statements not specific to this paper
   - Include methodology details in findings or vice versa
   - Pad responses with unnecessary context

Labels to extract:
{labels_text}

Response format for EACH label:
- summary: Direct answer (or "N/A" if not applicable)
- key_points: Array of short fragments (or empty [] if N/A)
- extracted_items: Structured data if applicable (or empty [] if N/A)
- sources: Page/section references (or empty [] if N/A)

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