"""Given a label, do a similarity search on the vector DB and extract 10 most concerned chunks"""

# app/services/data_extraction/search.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_openai import OpenAIEmbeddings
from supabase import Client, create_client

from app.constants import EMBED_MODEL, QUERY_RPC
logger = logging.getLogger(__name__)
from app.config import settings



_embeddings = OpenAIEmbeddings(
    model=EMBED_MODEL,
    api_key=settings.openai_api_key,   # <-- snake_case field recommended
)
_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = settings.supabase_url
        key = settings.supabase_service_role_key  # must be service role on server
        _supabase = create_client(url, key)
    return _supabase


def fetch_relevant_chunks(
    label: str,
    k: int = 1,
    filter_doc_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Given a label, run similarity search in Supabase and return top-k chunks with scores.
    Returns: [{ "text": ..., "metadata": {...}, "similarity": float, "id": <uuid> }, ...]
    """
    if not label or not label.strip():
        return []

    # 1) Embed the label
    qvec = _embeddings.embed_query(label)

    # 2) Call RPC (uses pgvector index)
    params = {
        "query_embedding": qvec,
        "match_count": k,
        "filter": {"doc_id": filter_doc_id} if filter_doc_id else None,
    }
    try:
        res = _get_supabase().rpc(QUERY_RPC, params).execute()
        rows = res.data or []  # <- No .error; just use .data
    except Exception as e:
        # Optional: log and re-raise as 500 upstream
        # logger.exception("Supabase RPC failed")
        raise

    logger.info(f"RES {res}")
    # 3) Normalize output
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row.get("id"),
                "text": row.get("content"),
                "metadata": row.get("metadata") or {},
                "similarity": row.get("similarity"),
            }
        )

    logger.info(f"OUT {out}")
    return out
