from app.schemas.schemas import FetchByDoisInput, FetchByDoisResponse
import json
from typing import List, Optional
from app.schemas.lens_api_request import UserLensSearchInput
from app.schemas.search_response import EnrichedSearchResponse, PaginationMetadata
from app.schemas.lens_api_response import ScholarResponse
from app.schemas.schemas import GenerateSearchScopeInput, GenerateSearchScopeResponse
from app.services.lens_client import LensAPIClient, build_lens_request, build_lens_request_v2, build_doi_search_request
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
import os
from datetime import datetime
from openai import OpenAI
from app.config import settings
import random

from app.database import get_db, User
from app.schemas.user import UserResponse, UserUpdate, UserCreate
from app.supabase_auth import get_current_user_from_supabase, get_optional_user

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

# FT50 ISSN numbers for Financial Times Top 50 journals
FT50_ISSN_NUMBERS = [
    "00014273", "00018392", "00028282", "00129682", "00178012", "00187267", "00218456", "00219010",
    "00221082", "00221090", "00222380", "00222429", "00222437", "00223808", "00251909", "0030364X",
    "00335533", "00346527", "00472506", "00487333", "00904848", "00920703", "00935301", "01432095",
    "01492063", "01654101", "01674544", "01708406", "02726963", "0304405X", "03613682", "03637425",
    "07322399", "07421222", "07495978", "08239150", "08839026", "08939454", "10422587", "10477039",
    "10477047", "10577408", "10591478", "10959920", "10970266", "1099050X", "13806653", "14657368",
    "14676486", "1467937X", "14680262", "1475679X", "14786990", "15234614", "15265455", "15265463",
    "1526548X", "15265498", "15265501", "15265536", "15265544", "15314650", "15327663", "15375277",
    "1537534X", "15406261", "15406520", "15477185", "15477193", "15527824", "15571211", "1557928X",
    "15723097", "15730697", "1573692X", "15737136", "1741282X", "17413044", "17566916", "18731317",
    "19113846", "19303815", "19324391", "1932443X", "19375956", "19391854", "19447981", "02767783",
    "21629730", "15329194", "00014826", "15587967"
]

HEC_Accounting_ISSN_NUMBERS = [
        "00014273","00014826","00018392","00027766","00028282","00029602","00030554","00031224","00063444","00129682",
        "00130133","0017811X","00189391","00206598","00218456","00219010","00219460","00220515","00220531","00221090",
        "0022166X","00221996","00222380","00222429","00222437","00223514","00223808","00251909","00255610","0030364X",
        "00315826","00335533","00346527","00346535","00377732","00472506","00472727","00487333","00905364","00911798",
        "00935301","01432095","01621459","01650750","01654101","01678116","02726963","03043878","03043932","0304405X",
        "03044076","03075400","03613682","03637425","0364765X","03772217","07322399","0734306X","07421222","07495978",
        "08239150","08839026","08939454","08943796","08953309","08998256","09567976","0960085X","09638180","10477039",
        "10477047","10489843","10577408","10902473","10957235","10959920","10970266","10991379","13501917","13515993",
        "13652575","13806653","14364646","14643510","14657368","14676486","14679280","1467937X","14680262","14680297",
        "14680386","14682354","14684497","1475679X","14769344","14786990","15234614","15265455","15265463","15265471",
        "1526548X","15265498","15265501","15265536","15309142","15314650","15327663","15347605","15369323","1537274X",
        "15375277","15375307","1537534X","15375390","15375943","15424766","15424774","15477185","15477193","15488004",
        "1557928X","15580040","15587967","15723097","1573692X","15737136","17446570","17566916","18726895","18730353",
        "18731317","18758320","19113846","19303815","19391854","19398271","19447981","2754205X","00221082","15406261",
        "14679868", "13697412","02767783, 21629730","10591478","19375956","17562171","07416261","10957138","03630129",
        "00036056"
]

IS_Information_Systems_ISSN_NUMBERS = [
    "02767783", "15265455", "0960085X", "09638180", "07421222", "15587967", "13652575", "14680386", "02683962", "14664437"
]


    
@router.post("/advanced_search", response_model=EnrichedSearchResponse)
async def dynamic_lens_advanced_search(input: UserLensSearchInput) -> EnrichedSearchResponse:
    """
    Dynamic search route that returns enriched results with pagination metadata.
    """
    try:
        client = LensAPIClient()

        sanitized_input = sanitize_for_logging(input.model_dump())
        logger.info(f"Input Payload: {sanitized_input}")
        if input.query_string:
                    input.query_string = input.query_string.strip()
                    if input.query_string.startswith('AND '):
                        input.query_string = input.query_string[4:]  # Remove 'AND '
                        logger.warning(f"Removed leading AND from query_string")
                    elif input.query_string.startswith('OR '):
                        input.query_string = input.query_string[3:]  # Remove 'OR '
                        logger.warning(f"Removed leading OR from query_string")
                    logger.info(f"Sanitized query_string: {input.query_string}")
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
                logger.info(f"  - First 5 ISSNs: {input.accepted_issns[:5]}")
            
            # Warning if too many ISSNs
            if len(input.accepted_issns) > 150:
                logger.warning(f"Large number of ISSNs ({len(input.accepted_issns)}). This might cause API issues.")
        request_payload = build_lens_request_v2(input)
        sanitized_payload = sanitize_for_logging(request_payload)
        logger.info(f"Request Payload: {sanitized_payload}")

        api_response = client.search(request_payload)
        
        # Parse the raw data into ScholarResponse objects with error handling
        parsed_articles = []
        for item in api_response.data:
            try:
                # Fill in missing required fields with defaults
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

                parsed_articles.append(ScholarResponse(**item))
            except Exception as e:
                logger.warning(f"Failed to parse article: {e}, skipping item")
                continue
        
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
            model="gpt-4o-mini",
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

            logger.info(f"Generated search scope filters: {filters_data}")

            return GenerateSearchScopeResponse(
                success=True,
                filters=filters_data,
                reasoning="Filters generated based on review topic analysis"
            )

        except json.JSONDecodeError as e:
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
        parsed_articles = []
        for item in api_response.data:
            try:
                # Fill in missing required fields with defaults (same as advanced_search)
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


                parsed_article = ScholarResponse(**item)
                parsed_articles.append(parsed_article)

                # Extract DOI from external_ids - keep original case
                if parsed_article.external_ids:
                    for ext_id in parsed_article.external_ids:
                        if ext_id.type.lower() == 'doi':
                            found_dois.add(ext_id.value)

            except Exception as e:
                logger.warning(f"Failed to parse article: {e}, item: {item}")
                continue

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