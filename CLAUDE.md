# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIR³ backend is a FastAPI service powering the systematic literature review platform. It handles paper search (via Lens.org), PDF ingestion and chunking, AI-powered data extraction, and review section generation.

## Commands

```bash
uv sync                              # Install dependencies
make run                             # Start API server on port 8000
make test                            # Run test suite
uv run pytest tests/test_main.py     # Run a single test file
uv run pytest -v                     # Verbose
uv run pytest --cov=app              # With coverage
uv run ruff check .                  # Lint
uv run mypy app                      # Type check
```

API docs: `http://localhost:8000/docs`

## Environment Setup

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite (default: `sqlite:///./app.db`) or PostgreSQL |
| `JOURNALS_DATABASE_URL` | Journal metadata DB (`sqlite:///./journals.db`) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_KEY` | Supabase API keys |
| `SUPABASE_JWT_SECRET` | For JWT validation |
| `OPENAI_API_KEY` | GPT-4o and embeddings |
| `LENS_API_KEY` / `LENS_API_TOKEN` | Lens.org scholar search |

---

## Architecture

```
Request → Middleware (CORS, TrustedHost)
        → Router (path matching)
        → Dependency Resolution (DB session, auth)
        → Handler
        → Service Layer
        → External APIs / Supabase / OpenAI
        → Pydantic Response
```

### Layers

- **Routers** (`app/routers/`) — thin handlers, input validation, HTTP concerns only
- **Services** (`app/services/`) — all business logic and AI pipelines
- **Schemas** (`app/schemas/`) — Pydantic models for request/response validation
- **Database** (`app/database.py`) — SQLAlchemy models for local SQLite/PostgreSQL

### Auth

`app/supabase_auth.py` validates Supabase JWTs from the `Authorization: Bearer` header. `get_current_user` is a FastAPI dependency used to gate protected endpoints. `get_optional_user` is used on public endpoints that optionally accept auth.

### Databases

| Database | Engine | Purpose |
|---|---|---|
| `app.db` | SQLite / PostgreSQL | Users, Items |
| `journals.db` | SQLite | Journal rankings and category pairs |
| Supabase (PostgreSQL + pgvector) | Cloud | Paper chunks (embeddings), paper metadata, review data |

---

## API Endpoints

**Base path**: `/api/v1/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| GET | `/api/v1/users/` | No | List users |
| GET | `/api/v1/users/me` | Yes | Current user profile |
| POST | `/api/v1/papers/advanced_search` | No | Search papers via Lens.org |
| POST | `/api/v1/papers/generate_search_scope` | No | AI-suggested search scope |
| POST | `/api/v1/papers/fetch_by_doi` | No | Fetch paper by DOI |
| POST | `/api/v1/pdf/extract-pdf-metadata` | No | Extract metadata from PDF |
| POST | `/api/v1/data/extract-paper-data` | No | Extract data from a paper |
| POST | `/api/v1/data/batch-extract-paper-data` | No | Batch extract multiple labels |
| POST | `/api/v1/data/download-paper` | No | Download PDF from Supabase storage |
| GET | `/api/v1/journals/issns` | No | Get ISSNs by field/quartile |
| POST | `/api/v1/review/generate-section-content` | Yes | Generate review section draft |

---

## User / Request Flow

```
Frontend (air_cube)
      │
      ├─ Auth: Supabase login → JWT token
      │
      ├─ Paper Search
      │   POST /api/v1/papers/advanced_search
      │   └─ Lens.org API → paginated results with journal metadata
      │
      ├─ Paper Ingestion (on data extraction request)
      │   POST /api/v1/data/extract-paper-data
      │   └─ Download PDF from Supabase storage
      │       → Parse text (PyMuPDF)
      │       → Chunk (500 tokens, 200 overlap)
      │       → Embed (text-embedding-3-small)
      │       → Store in Supabase pgvector (paper_chunks)
      │       → Similarity search → LLM refinement → result
      │
      ├─ Batch Extraction
      │   POST /api/v1/data/batch-extract-paper-data
      │   └─ Full PDF text → GPT-4o extracts all labels at once
      │
      └─ Review Writing
          POST /api/v1/review/generate-section-content
          └─ Load prior sections for context
              → LangChain + GPT-4o generates section content
              → Store in Supabase sections table
```

---

## File Descriptions

### Root

| File | Description |
|---|---|
| `main.py` | Thin entry point importing from `app.main` |
| `run.py` | Alternative entry point using uvicorn directly |
| `load_journals.py` | One-off script to populate `journals.db` from remote CSV sources |
| `check_journals.py` | Utility script to verify journal database state |
| `Makefile` | `make run` and `make test` shortcuts using `uv` |
| `pyproject.toml` | Project dependencies and metadata (uv-managed) |
| `SUPABASE_INTEGRATION.md` | Frontend integration guide with auth examples |

### `app/`

| File | Description |
|---|---|
| `main.py` | FastAPI app factory: registers routers, CORS/TrustedHost middleware, global exception handlers, lifespan DB init |
| `config.py` | `Settings` class (pydantic-settings) loading all env vars with defaults |
| `database.py` | SQLAlchemy models (`User`, `Item`, `Journal`, `Category_Pairs`) and session factory for both DBs |
| `supabase_auth.py` | JWT decode, `get_current_user` and `get_optional_user` FastAPI dependencies |
| `constants.py` | Shared constants: chunk size (500), overlap (200), embedding model name, Supabase RPC names |

### `app/routers/`

| File | Description |
|---|---|
| `users.py` | `GET /users/` and `GET /users/me` — user listing and profile retrieval |
| `papers.py` | Paper search endpoints: advanced search, scope generation, DOI/Lens ID fetch, related categories |
| `pdf.py` | `POST /pdf/extract-pdf-metadata` — extracts title, abstract, authors from uploaded PDF using PyMuPDF |
| `data_ingestion.py` | Extraction endpoints: single-label extraction, batch multi-label extraction, PDF download |
| `journals.py` | Journal metadata: get ISSNs by field/quartile, search journals, load/empty DB |
| `review_generation.py` | `POST /review/generate-section-content` — triggers LangChain review section generation |

### `app/schemas/`

| File | Description |
|---|---|
| `user.py` | `SupabaseUser`, `UserBase`, `UserCreate`, `UserResponse` models |
| `schemas.py` | `GenerateSearchScopeRequest`, DOI/Lens fetch request models |
| `lens_api_request.py` | Full Lens.org query builder schema (boolean terms, ranges, filters, sorting) |
| `lens_api_response.py` | `ScholarResponse` and nested models mapping raw Lens API JSON |
| `search_response.py` | `EnrichedSearchResponse` with `PaginationMetadata` |
| `review_generation.py` | `GenerateSectionRequest`, `GenerateSectionResponse`, context models |
| `ingestion.py` | Request/response models for data extraction endpoints |
| `item.py` | `ItemCreate`, `ItemResponse` models |

### `app/services/`

| File | Description |
|---|---|
| `lens_client.py` | `LensAPIClient` — builds and sends POST requests to Lens.org, handles auth, parses responses |
| `journals.py` | Journal DB queries: get ISSNs by field/quartile, related categories, full-text journal search |

### `app/services/data_extraction/`

| File | Description |
|---|---|
| `main.py` | Orchestrates extraction: checks for existing chunks, calls ingestion if needed, runs retrieval + refinement |
| `fetch.py` | Supabase pgvector similarity search via `match_documents` RPC |
| `refine.py` | LangChain `RefineDocumentsChain` — iteratively refines extracted content across retrieved chunks |
| `prompts.py` | LangChain prompt templates and output format instructions for extraction |

### `app/services/data_ingestion/`

| File | Description |
|---|---|
| `main.py` | Top-level `ingest_paper()` — coordinates parse → chunk → embed → store |
| `read.py` | `read_paper_pdf_file()` — reads PDF bytes with PyMuPDF, returns structured document |
| `process.py` | `chunk_document()` — splits document using `RecursiveCharacterTextSplitter` with tiktoken |
| `store.py` | `store_in_vector_db()` — embeds chunks with OpenAI, stores in Supabase `paper_chunks` |
| `types.py` | Internal types: `PdfFile`, `PdfDocument`, `Chunk` |
| `utils.py` | Text and metadata sanitization helpers (clean strings, normalize ISSN lists, etc.) |

### `app/services/review_generation/`

| File | Description |
|---|---|
| `main.py` | `ReviewGenerationService` — uses LangChain + GPT-4o (temp 0.3) to generate academic section content, with prior-section context for coherence |

### `tests/`

| File | Description |
|---|---|
| `conftest.py` | Pytest fixtures (test client, DB setup) |
| `conftest_simple.py` | Simplified fixtures for lightweight tests |
| `test_main.py` | Core API endpoint tests (health, users, items) |
| `test_lens_client.py` | Unit tests for Lens API client and query building |
| `test_journals.py` | Journal service and ISSN lookup tests |
| `test_search_endpoints.py` | Integration tests for paper search endpoints |
| `test_schemas.py` | Pydantic schema validation tests |
| `test_boolean_queries.py` | Boolean query construction tests |
| `fixtures/test_queries.py` | Reusable search query fixtures |
| `fixtures/lens_api_responses.py` | Mock Lens API response payloads |
