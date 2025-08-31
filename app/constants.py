"""Data pipeline constants used across the application."""



# DATA EXTRACTION
## Chunking Configuration
CHUNK_SIZE = 200
CHUNK_OVERLAP = 25

## Embedding Configuration  
EMBED_MODEL = "text-embedding-3-small"

## Database Configuration
TABLE_NAME = "z_documents"  # LangChain non-default (documents is default)
QUERY_RPC = "match_documents"  # LangChain default RPC name