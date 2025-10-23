import json
from typing import List, Optional
from app.schemas.lens_api_request import UserLensSearchInput
from app.schemas.search_response import EnrichedSearchResponse, PaginationMetadata
from app.schemas.lens_api_response import ScholarResponse
from app.services.lens_client import LensAPIClient, build_lens_request, build_lens_request_v2
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db, User
from app.schemas.user import UserResponse, UserUpdate, UserCreate
from app.supabase_auth import get_current_user_from_supabase, get_optional_user

router = APIRouter()
logger = logging.getLogger(__name__)

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

    
@router.post("/advanced_search", response_model=EnrichedSearchResponse)
async def dynamic_lens_advanced_search(input: UserLensSearchInput) -> EnrichedSearchResponse:
    """
    Dynamic search route that returns enriched results with pagination metadata.
    """
    try:
        client = LensAPIClient()

        logger.info(f"Input PAyload: {input}")

        # Handle FT50 ranking: override accepted_issns and clear journal_tier/fields_of_study
        if input.ranking == "FT50":
            logger.info("FT50 ranking detected - overriding with FT50 ISSN list and clearing journal_tier/fields_of_study")
            input.accepted_issns = FT50_ISSN_NUMBERS.copy()
            input.journal_tier = None
            input.fields_of_study = None
            logger.info(f"Set accepted_issns to {len(input.accepted_issns)} FT50 ISSN numbers")
        if hasattr(input, 'accepted_issns') and input.accepted_issns:
            original_count = len(input.accepted_issns)
            unique_issns = list(set(input.accepted_issns))
            unique_count = len(unique_issns)
            
            logger.info(f"ISSN Analysis:")
            logger.info(f"  - Original ISSN count: {original_count}")
            logger.info(f"  - Unique ISSN count: {unique_count}")
            logger.info(f"  - Duplicates found: {original_count - unique_count}")
            
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
            if len(input.accepted_issns) > 100:
                logger.warning(f"Large number of ISSNs ({len(input.accepted_issns)}). This might cause API issues.")
        request_payload = build_lens_request_v2(input)

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