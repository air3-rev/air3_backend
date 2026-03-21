import logging
from typing import List, Optional

from app.constants import EMBED_MODEL, QUERY_RPC, TABLE_NAME
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from supabase import Client, create_client
from app.config import settings
from app.services.data_ingestion.utils import sanitize_metadata, sanitize_text

logger = logging.getLogger(__name__)

_supabase: Optional[Client] = None
_embeddings_model: Optional[OpenAIEmbeddings] = None
_vectorstore: Optional[SupabaseVectorStore] = None


def _get_supabase_client() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _supabase


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings_model
    if _embeddings_model is None:
        _embeddings_model = OpenAIEmbeddings(
            model=EMBED_MODEL,
            api_key=settings.openai_api_key,
        )
    return _embeddings_model


def get_vectorstore() -> SupabaseVectorStore:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = SupabaseVectorStore(
            client=_get_supabase_client(),
            embedding=_get_embeddings(),
            table_name=TABLE_NAME,
            query_name=QUERY_RPC,
        )
    return _vectorstore


def sanitize_document(doc: Document) -> Document:
    """
    Sanitize a document's content and metadata to ensure database compatibility.
    """
    # Sanitize page content
    sanitized_content = sanitize_text(doc.page_content)

    # Sanitize metadata recursively
    sanitized_metadata = sanitize_metadata(doc.metadata)

    return Document(
        page_content=sanitized_content,
        metadata=sanitized_metadata
    )


def chunks_exist_for_paper(paper_id: str) -> bool:
    """Check if chunks already exist for a given paper_id."""
    sb = _get_supabase_client()
    existing = sb.table(TABLE_NAME).select("id").filter(
        "metadata->>paper_id", "eq", paper_id
    ).limit(1).execute()
    return bool(existing.data)


def store_in_vector_db(docs: List[Document]):
    """Store embeddings and metadata in the vector database.

    Skips insertion if chunks for the paper_id already exist (idempotent).
    """
    if not docs:
        return

    # Check for existing chunks by paper_id
    paper_id = docs[0].metadata.get("paper_id")
    if paper_id and chunks_exist_for_paper(paper_id):
        logger.info("Chunks already exist for paper %s, skipping ingestion", paper_id)
        return

    # Sanitize all documents before storing
    sanitized_docs = [sanitize_document(doc) for doc in docs]

    get_vectorstore().add_documents(sanitized_docs)
    
