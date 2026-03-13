# AIR³ Backend

FastAPI backend for AIR³ — a systematic literature review automation platform. Handles paper discovery via Lens.org, PDF ingestion, AI-powered data extraction, and review section generation.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Language | Python 3.13+ |
| Package manager | `uv` |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Databases | SQLite (default) / PostgreSQL + Supabase (pgvector) |
| Auth | Supabase JWTs (PyJWT) |
| AI / LLM | LangChain + OpenAI GPT-4o |
| PDF Processing | PyMuPDF |
| Paper Search | Lens.org API |
| Validation | Pydantic v2 |
| Linting | Ruff |
| Type checking | mypy |
| Testing | pytest |

## Project Structure

```
air3_backend/
├── app/
│   ├── main.py              # FastAPI app factory, CORS, middleware
│   ├── config.py            # Settings (pydantic-settings, loads .env)
│   ├── database.py          # SQLAlchemy models (User, Item, Journal, Category_Pairs)
│   ├── supabase_auth.py     # JWT validation FastAPI dependencies
│   ├── constants.py         # Chunk size, overlap, embedding model names
│   ├── schemas/             # Pydantic request/response models
│   ├── routers/             # Thin route handlers (delegate to services)
│   │   ├── users.py
│   │   ├── papers.py
│   │   ├── pdf.py
│   │   ├── data_ingestion.py
│   │   ├── journals.py
│   │   └── review_generation.py
│   └── services/            # Business logic and AI pipelines
│       ├── lens_client.py   # Lens.org API integration
│       ├── journals.py      # Journal metadata queries
│       ├── data_extraction/ # PDF → text → GPT-4o refinement
│       ├── data_ingestion/  # PDF parse → chunk → embed → store
│       └── review_generation/ # LangChain review section generation
├── tests/
├── pyproject.toml
├── Makefile
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Set up environment
cp .env.example .env
# Fill in required values (see Environment Variables below)

# 3. Run the server
make run
# or: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Commands

```bash
uv sync                          # Install dependencies
make run                         # Start dev server (port 8000, auto-reload)
make test                        # Run test suite
uv run pytest tests/test_main.py # Run a single test file
uv run pytest -v                 # Verbose output
uv run pytest --cov=app          # With coverage
uv run ruff check .              # Lint
uv run mypy app                  # Type check
```

## Environment Variables

Copy `.env.example` to `.env`. Settings are loaded from `.env.local` then `.env`.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | No | `sqlite:///./app.db` | Primary DB (users, items) |
| `JOURNALS_DATABASE_URL` | No | `sqlite:///./journals.db` | Journal rankings DB |
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | — | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | — | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Yes | — | JWT validation secret |
| `OPENAI_API_KEY` | Yes | — | GPT-4o and embeddings |
| `LENS_URL` | Yes | — | Lens.org API base URL |
| `LENS_TOKEN` | Yes | — | Lens.org API token |
| `CORS_ORIGINS` | No | `["*"]` | Allowed CORS origins |
| `DEBUG` | No | `false` | Debug mode |
| `PORT` | No | `8000` | Server port |

## API Endpoints

### System
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | No | API info |
| GET | `/health` | No | Health check |

### Users
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/users/list` | No | List all users (paginated) |
| GET | `/api/v1/users/list/{user_id}` | No | Get user by ID |
| GET | `/api/v1/users/me` | Yes | Current user profile |

### Papers
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/papers/advanced_search` | No | Search papers via Lens.org (filters: ranking, ISSNs, date range, fields of study) |
| POST | `/api/v1/papers/generate_search_scope` | Yes | AI-suggested search scope based on review topic |
| POST | `/api/v1/papers/fetch_by_dois` | No | Fetch papers by DOI list |
| POST | `/api/v1/papers/fetch_by_lens_ids` | No | Fetch papers by Lens ID list |

### PDF
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/pdf/extract-pdf-metadata` | No | Extract title, abstract, authors from uploaded PDF |
| POST | `/api/v1/pdf/debug-pdf-text` | No | Debug raw text extraction from PDF |

### Data Extraction
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/data/extract-paper-data` | No | Extract a single label from a paper (auto-ingests if not yet chunked) |
| POST | `/api/v1/data/batch-extract-paper-data` | No | Extract multiple labels from a paper at once |
| POST | `/api/v1/data/download-and-store-pdf` | No | Download PDF from URL and store in Supabase storage |
| POST | `/api/v1/data/test-pdf-download` | No | Test if a PDF URL is accessible |

### Journals
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/journals/journals` | No | Get ISSNs by field and quartile |
| GET | `/api/v1/journals/categories/related` | No | Related categories by co-occurrence |
| GET | `/api/v1/journals/search` | No | Search journals by name |
| GET | `/api/v1/journals/issns` | No | Get ISSNs by journal title |
| GET | `/api/v1/journals/ranking/{ranking}` | No | Journal titles for a ranking (FT50, HEC, IS) |
| POST | `/api/v1/journals/load` | No | Load journal data into DB from remote sources |
| POST | `/api/v1/journals/empty` | No | Clear all journal data from DB |

### Review Generation
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/review/generate-section-content` | Yes | Generate a review section using LangChain + GPT-4o (context-aware with prior sections) |
| GET | `/api/v1/review/health` | No | Health check for review service |

## Authentication

Protected endpoints require a Supabase JWT in the `Authorization: Bearer <token>` header. The token is validated against `SUPABASE_JWT_SECRET` in `app/supabase_auth.py`.

## Databases

| DB | Default | Purpose |
|---|---|---|
| `app.db` | `sqlite:///./app.db` | Users and items |
| `journals.db` | `sqlite:///./journals.db` | Journal rankings (SJR/Scimago) |
| Supabase | Cloud PostgreSQL + pgvector | Paper chunks (embeddings), paper metadata, review sections |

Tables are created automatically on startup for SQLite/PostgreSQL. Supabase schema is managed separately.

## AI Pipeline

```
Paper ingestion:
  PDF URL → PyMuPDF (text extraction)
          → RecursiveCharacterTextSplitter (500 tokens, 200 overlap)
          → OpenAI text-embedding-3-small
          → Supabase pgvector (paper_chunks table)

Data extraction:
  Label + paper_id → pgvector similarity search
                   → LangChain RefineDocumentsChain
                   → GPT-4o → structured result

Review generation:
  Section request + prior sections → LangChain + GPT-4o (temp 0.3) → draft content
```

## Docker

```bash
docker-compose up -d
```

Starts:
- `api` — FastAPI on port 8000
- `db` — PostgreSQL 15 on port 5432
- `redis` — Redis 7 on port 6379
- `nginx` — Reverse proxy on port 80

## Testing

```bash
make test                        # All tests
uv run pytest -v                 # Verbose
uv run pytest --cov=app          # With coverage report
uv run pytest tests/test_main.py # Single file
```
