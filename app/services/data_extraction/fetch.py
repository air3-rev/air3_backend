"""Given a label, do a similarity search on the vector DB and extract 10 most concerned chunks"""

# app/services/data_extraction/search.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_openai import OpenAIEmbeddings
from supabase import Client, create_client

from app.constants import EMBED_MODEL, QUERY_RPC
from app.config import settings

from app.services.data_ingestion.types import Chunk


logger = logging.getLogger(__name__)
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
) -> List[Chunk]:
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
        "filter": {"paper_id": filter_doc_id} if filter_doc_id else None,
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



# --- Fetch chunks from Supabase ---
def fetch_paper_chunks(
    label: str,
    k: int = 5,
    paper_id: Optional[str] = None
) -> List[Chunk]:
    """
    Given a label and paper_id, fetch top-k most relevant chunks from Supabase.
    Returns a list of dicts with keys: id, text, metadata, similarity.
    """
    if not label.strip():
        return []

    # 1️⃣ Embed the label
    query_embedding = _embeddings.embed_query(label)

    # 2️⃣ Call Supabase RPC for similarity search
    params = {
        "query_embedding": query_embedding,
        "match_count": k,
        "filter": {"paper_id": paper_id} if paper_id else None,
        # "filter": {"metadata->>'paper_id'": paper_id} if paper_id else None,

    }

    try:
        res = _get_supabase().rpc("match_chunks", params).execute()
        rows = res.data or []
    except Exception as e:
        logger.exception("Supabase RPC failed for label '%s'", label)
        raise

    logger.debug("Supabase RPC response: %s", rows)

    # 3️⃣ Normalize output into chunk format
    chunks: List[Dict[str, Any]] = []
    for row in rows:
        chunks.append(
            {
                "id": row.get("id"),
                "text": row.get("content"),
                "metadata": row.get("metadata") or {},
                "similarity": row.get("similarity"),
            }
        )

    logger.debug("Normalized chunks: %s", chunks)
    return chunks
