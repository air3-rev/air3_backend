"""Given a label, do a similarity search on the vector DB and extract 10 most concerned chunks"""

# app/services/data_extraction/search.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from supabase import Client, create_client

logger = logging.getLogger(__name__)

load_dotenv()
EMBED_MODEL = (
    "text-embedding-3-small"  # 1536-dim recommended (HNSW supports <= 2000 dims)
)
RPC_NAME = "match_documents"

_embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # must be service role on server
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
        res = _get_supabase().rpc(RPC_NAME, params).execute()
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
