from app.schemas.schemas import FetchByDoisInput, FetchByDoisResponse, FetchByLensIdsInput, FetchByLensIdsResponse
import json
from app.schemas.lens_api_request import UserLensSearchInput
from app.schemas.search_response import EnrichedSearchResponse, PaginationMetadata
from app.schemas.lens_api_response import ScholarResponse
from app.schemas.schemas import GenerateSearchScopeInput, GenerateSearchScopeResponse
from app.services.lens_client import LensAPIClient, build_lens_request_v2, build_doi_search_request, build_lens_id_search_request
from fastapi import APIRouter, Depends, HTTPException
import logging
import os
from datetime import datetime
from openai import OpenAI
from app.config import settings
import random

from app.database import User
from app.supabase_auth import get_current_user_from_supabase
from app.lib.issn_lists import FT50_ISSN_NUMBERS, HEC_Accounting_ISSN_NUMBERS, IS_Information_Systems_ISSN_NUMBERS

router = APIRouter()
logger = logging.getLogger(__name__)

def sanitize_for_logging(data):
    """
    Sanitize data for logging by truncating long ISSN lists to first 3 items and total count.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if k == 'accepted_issns' and isinstance(v, list):
                if len(v) > 3:
                    sanitized[k] = f"{v[:3]}... (total: {len(v)})"
                else:
                    sanitized[k] = v
            elif isinstance(v, dict) and 'source.issn' in v and isinstance(v['source.issn'], list):
                # Handle nested terms with source.issn
                issns = v['source.issn']
                if len(issns) > 3:
                    new_v = v.copy()
                    new_v['source.issn'] = f"{issns[:3]}... (total: {len(issns)})"
                    sanitized[k] = new_v
                else:
                    sanitized[k] = v
            else:
                sanitized[k] = sanitize_for_logging(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]
    else:
        return data

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.openai_api_key)


def _parse_articles(raw_data: list) -> list[ScholarResponse]:
    """Parse raw Lens API data into ScholarResponse objects with default filling."""
    parsed = []
    for item in raw_data:
        try:
            if 'authors' in item and item['authors']:
                for author in item['authors']:
                    if 'collective_name' not in author:
                        author['collective_name'] = None
                    if 'affiliations' not in author:
                        author['affiliations'] = []
            if 'source' in item and item['source']:
                source = item['source']
                if 'type' not in source:
                    source['type'] = None
                if 'issn' not in source:
                    source['issn'] = []
                if 'country' not in source:
                    source['country'] = None
                if 'asjc_codes' not in source:
                    source['asjc_codes'] = None
                if 'asjc_subjects' not in source:
                    source['asjc_subjects'] = None
            if 'references' in item and item['references']:
                for ref in item['references']:
                    if 'text' not in ref:
                        ref['text'] = None
            parsed.append(ScholarResponse(**item))
        except Exception as e:
            logger.warning(f"Failed to parse article: {e}, skipping item")
    return parsed


@router.post("/advanced_search", response_model=EnrichedSearchResponse)
async def dynamic_lens_advanced_search(input: UserLensSearchInput) -> EnrichedSearchResponse:
    """
    Dynamic search route that returns enriched results with pagination metadata.
    """
    try:
        client = LensAPIClient()

        sanitized_input = sanitize_for_logging(input.model_dump())
        logger.debug(f"Input Payload: {sanitized_input}")
        if input.query_string:
                    input.query_string = input.query_string.strip()
                    if input.query_string.startswith('AND '):
                        input.query_string = input.query_string[4:]  # Remove 'AND '
                        logger.warning("Removed leading AND from query_string")
                    elif input.query_string.startswith('OR '):
                        input.query_string = input.query_string[3:]  # Remove 'OR '
                        logger.warning("Removed leading OR from query_string")
                    logger.debug(f"Sanitized query_string: {input.query_string}")
        # Handle FT50 ranking: override accepted_issns and clear journal_tier/fields_of_study
        if input.ranking == "FT50":
            logger.info("FT50 ranking detected - overriding with FT50 ISSN list and clearing journal_tier/fields_of_study")
            input.accepted_issns = FT50_ISSN_NUMBERS.copy()
            input.journal_tier = None
            input.fields_of_study = None
            logger.info(f"Set accepted_issns to {len(input.accepted_issns)} FT50 ISSN numbers")
        elif input.ranking == "HEC":
            logger.info("HEC ranking detected - overriding with HEC ISSN list and clearing journal_tier/fields_of_study")
            input.accepted_issns = HEC_Accounting_ISSN_NUMBERS.copy()
            input.journal_tier = None
            input.fields_of_study = None
            logger.info(f"Set accepted_issns to {len(input.accepted_issns)} HEC Business, Accounting and Management ISSN numbers")
        elif input.ranking == "IS":
            logger.info("IS ranking detected - overriding with IS ISSN list and clearing journal_tier/fields_of_study")
            input.accepted_issns = IS_Information_Systems_ISSN_NUMBERS.copy()
            input.journal_tier = None
            input.fields_of_study = None
            logger.info(f"Set accepted_issns to {len(input.accepted_issns)} IS Information Systems ISSN numbers")
        if hasattr(input, 'accepted_issns') and input.accepted_issns:
            original_count = len(input.accepted_issns)
            unique_issns = list(set(input.accepted_issns))
            unique_count = len(unique_issns)
            
            
            if original_count != unique_count:
                logger.warning(f"Found {original_count - unique_count} duplicate ISSNs, removing them")
                # Find which ones are duplicated
                from collections import Counter
                issn_counts = Counter(input.accepted_issns)
                duplicates = {issn: count for issn, count in issn_counts.items() if count > 1}
                logger.warning(f"Duplicate ISSNs: {duplicates}")
                
                # Update input with unique ISSNs
                input.accepted_issns = unique_issns
            
            logger.info(f"  - Final ISSN count being sent to Lens API: {len(input.accepted_issns)}")
            
            # Log first few ISSNs for debugging
            if len(input.accepted_issns) > 0:
                logger.debug(f"  - First 5 ISSNs: {input.accepted_issns[:5]}")
            
            # Warning if too many ISSNs
            if len(input.accepted_issns) > 150:
                logger.warning(f"Large number of ISSNs ({len(input.accepted_issns)}). This might cause API issues.")
        request_payload = build_lens_request_v2(input)
        sanitized_payload = sanitize_for_logging(request_payload)
        logger.debug(f"Request Payload: {sanitized_payload}")

        api_response = client.search(request_payload)

        parsed_articles = _parse_articles(api_response.data)

        # Create pagination metadata
        pagination = PaginationMetadata.create(
            total=api_response.total,
            offset=input.offset or 0,
            size=input.size or 10
        )
        
        # Build the enriched response
        return EnrichedSearchResponse(
            data=parsed_articles,
            pagination=pagination,
            max_score=api_response.max_score
        )
    except Exception as e:
        logger.exception("Dynamic lens search failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate_search_scope", response_model=GenerateSearchScopeResponse)
async def generate_search_scope(
    input: GenerateSearchScopeInput,
    current_user: User = Depends(get_current_user_from_supabase)
) -> GenerateSearchScopeResponse:
    """
    Generate optimal search scope filters based on review information using OpenAI LLM.
    """
    try:
        logger.info(f"Generating search scope for review {input.review_id}")

        # Load categories from JSON file
        categories_file_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'categories.json')
        try:
            with open(categories_file_path, 'r') as f:
                available_categories = json.load(f)
        except FileNotFoundError:
            logger.warning("Categories file not found, using default categories")
            available_categories = [
                "Business and International Management",
                "Business, Management and Accounting (miscellaneous)",
                "Economics and Econometrics",
                "Finance",
                "Management Information Systems",
                "Marketing",
                "Strategy and Management"
            ]

        # Build context from review information
        context_parts = []
        if input.review_title:
            context_parts.append(f"Review Title: {input.review_title}")
        if input.review_description:
            context_parts.append(f"Review Description: {input.review_description}")
        if input.keyword_groups:
            keywords_text = []
            for i, group in enumerate(input.keyword_groups):
                if group.get('keywords'):
                    keyword_texts = [k.get('text', '') for k in group['keywords'] if k.get('text')]
                    if keyword_texts:
                        keywords_text.append(f"Group {i+1}: {' OR '.join(keyword_texts)}")
            if keywords_text:
                context_parts.append(f"Keywords: {'; '.join(keywords_text)}")

        context = "\n".join(context_parts) if context_parts else "No specific context provided"

        # Create the LLM prompt with available categories
        categories_sample = random.sample(available_categories, min(20, len(available_categories)))
        categories_list = "\n".join(f"- {cat}" for cat in sorted(categories_sample))

        prompt = f"""You are an expert research librarian helping to optimize search criteria for a systematic literature review.

Based on the following review information, recommend optimal search filter settings for academic literature search:

{context}

Please analyze the review topic and suggest appropriate filters from these categories:

1. **Publication Types**: Which types of publications should be included? (JournalArticle, ConferenceArticle, Book, etc.)
2. **Date Range**: What year range would be most appropriate? (from/to years)
3. **Journal Quality**: Which journal tiers should be included? (q1, q2, q3 - based on impact factor quartiles)
4. **Field of Study**: Select ONLY from the available academic fields listed below. Choose 2-4 most relevant fields that match the review topic.
5. **Open Access**: Should the search be limited to open access papers only?
6. **Search Fields**: Which fields should be searched? (title, abstract, full_text)
7. **Sort Order**: How should results be sorted? (relevance, citations, date, title)
8. **Minimum Citations**: Should there be a minimum citation threshold?

**Available Academic Fields:**
{categories_list}

Consider:
- The review's scope and methodology requirements
- Current academic publishing trends
- Quality vs. comprehensiveness trade-offs
- The need for recent, high-quality literature

IMPORTANT: For "field_of_study", you MUST select field names that exactly match from the available academic fields list above. Do not create or modify field names.

Provide your recommendations in JSON format with the following structure:
{{
  "publication_types": ["JournalArticle", "ConferenceArticle"],
  "open_access_only": false,
  "date_range": {{"from": "2015", "to": "2024"}},
  "journal_tier": ["q1", "q2"],
  "field_of_study": ["Business and International Management", "Strategy and Management"],
  "search_fields": ["title", "abstract"],
  "sort_by": "relevance",
  "min_citations": 0,
  "ranking": null
}}

Be conservative and practical in your recommendations. Focus on quality over quantity unless the topic suggests otherwise."""

        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model=settings.scope_generation_model,
            messages=[
                {"role": "system", "content": "You are a research methodology expert specializing in systematic literature review search strategies."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        # Extract the JSON response
        llm_response = response.choices[0].message.content.strip()

        # Try to parse the JSON response
        try:
            # Find JSON in the response (in case there's extra text)
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                filters_data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

            logger.debug(f"Generated search scope filters: {filters_data}")

            return GenerateSearchScopeResponse(
                success=True,
                filters=filters_data,
                reasoning="Filters generated based on review topic analysis"
            )

        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {llm_response}")
            # Return default filters if JSON parsing fails
            default_filters = {
                "publication_types": ["JournalArticle", "ConferenceArticle"],
                "open_access_only": False,
                "date_range": {"from": "2015", "to": str(datetime.now().year)},
                "journal_tier": ["q1", "q2"],
                "search_fields": ["title", "abstract"],
                "sort_by": "relevance",
                "min_citations": 0,
                "ranking": None
            }
            return GenerateSearchScopeResponse(
                success=True,
                filters=default_filters,
                reasoning="Used default filters due to parsing error"
            )
    except Exception as e:
        logger.exception("Dynamic lens search failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fetch_by_dois", response_model=FetchByDoisResponse)
async def fetch_papers_by_dois(input: FetchByDoisInput) -> FetchByDoisResponse:
    """
    Fetch papers by DOI numbers from Lens API.

    Returns found papers, count of found papers, count of not found papers,
    and list of DOIs that were not found.
    """
    try:
        if not input.dois:
            return FetchByDoisResponse(
                data=[],
                found_count=0,
                not_found_count=0,
                not_found_dois=[]
            )

        client = LensAPIClient()

        # Build the search request for DOIs
        request_payload = build_doi_search_request(input.dois)

        # Make the API call
        api_response = client.search(request_payload)

        # Extract DOIs from the found papers
        found_dois = set()
        parsed_articles = _parse_articles(api_response.data)
        for parsed_article in parsed_articles:
            # Extract DOI from external_ids - keep original case
            if parsed_article.external_ids:
                for ext_id in parsed_article.external_ids:
                    if ext_id.type.lower() == 'doi':
                        found_dois.add(ext_id.value)

        # Determine which DOIs were not found - keep original case for comparison
        input_dois_set = set(input.dois)
        not_found_dois = list(input_dois_set - found_dois)

        return FetchByDoisResponse(
            data=parsed_articles,
            found_count=len(parsed_articles),
            not_found_count=len(not_found_dois),
            not_found_dois=not_found_dois
        )

    except Exception as e:
        logger.exception("Fetch by DOIs failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch_by_lens_ids", response_model=FetchByLensIdsResponse)
async def fetch_papers_by_lens_ids(input: FetchByLensIdsInput) -> FetchByLensIdsResponse:
    """
    Fetch papers by Lens ID numbers from Lens API.

    Returns found papers, count of found papers, count of not found papers,
    and list of Lens IDs that were not found.
    """
    try:
        if not input.lens_ids:
            return FetchByLensIdsResponse(
                data=[],
                found_count=0,
                not_found_count=0,
                not_found_lens_ids=[]
            )

        client = LensAPIClient()

        # Build the search request for Lens IDs
        request_payload = build_lens_id_search_request(input.lens_ids)

        # Make the API call
        api_response = client.search(request_payload)

        # Extract Lens IDs from the found papers
        found_lens_ids = set()
        parsed_articles = _parse_articles(api_response.data)
        for parsed_article in parsed_articles:
            # Track found lens_id
            if parsed_article.lens_id:
                found_lens_ids.add(parsed_article.lens_id)

        # Determine which Lens IDs were not found
        input_lens_ids_set = set(input.lens_ids)
        not_found_lens_ids = list(input_lens_ids_set - found_lens_ids)

        return FetchByLensIdsResponse(
            data=parsed_articles,
            found_count=len(parsed_articles),
            not_found_count=len(not_found_lens_ids),
            not_found_lens_ids=not_found_lens_ids
        )

    except Exception as e:
        logger.exception("Fetch by Lens IDs failed")
        raise HTTPException(status_code=500, detail=str(e))