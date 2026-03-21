"""Data pipeline constants used across the application."""



# DATA EXTRACTION
## Chunking Configuration
CHUNK_SIZE = 500
CHUNK_OVERLAP = 200

## Embedding Configuration
# Import from config for centralized model management
from app.config import settings
EMBED_MODEL = settings.embedding_model

## Database Configuration
TABLE_NAME = "paper_chunks"  # LangChain non-default (documents is default)
QUERY_RPC = "match_chunks"  # RPC name used in Supabase pgvector search