import logging
import os
from typing import List

from app.constants import EMBED_MODEL, QUERY_RPC, TABLE_NAME
from dotenv import load_dotenv
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from supabase import Client, create_client

logger = logging.getLogger(__name__)

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]



embeddings_model = OpenAIEmbeddings(model=EMBED_MODEL)


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


def store_in_vector_db(docs: List[Document]):
    """Store embeddings and metadata in the vector database."""

    vectorstore.add_documents(docs)
