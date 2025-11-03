import logging
import os
from typing import List

from app.constants import EMBED_MODEL, QUERY_RPC, TABLE_NAME
from dotenv import load_dotenv
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from supabase import Client, create_client
from app.config import settings
from app.services.data_ingestion.utils import sanitize_metadata, sanitize_text

logger = logging.getLogger(__name__)



SUPABASE_URL =settings.supabase_url
SUPABASE_SERVICE_ROLE_KEY = settings.supabase_service_role_key



embeddings_model = OpenAIEmbeddings(
    model=EMBED_MODEL,
    api_key=settings.openai_api_key,   # <-- snake_case field recommended
)

supabase: Client = create_client(
    supabase_url=SUPABASE_URL, supabase_key=SUPABASE_SERVICE_ROLE_KEY
)


def get_vectorstore() -> SupabaseVectorStore:
    # Uses default table & RPC names;
    return SupabaseVectorStore(
        client=supabase,
        embedding=embeddings_model,
        table_name=TABLE_NAME,
        query_name=QUERY_RPC,
    )


vectorstore = get_vectorstore()


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


def store_in_vector_db(docs: List[Document]):
    """Store embeddings and metadata in the vector database."""

    # Sanitize all documents before storing
    sanitized_docs = [sanitize_document(doc) for doc in docs]

    vectorstore.add_documents(sanitized_docs)
    
