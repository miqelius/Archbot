# Multi-Agent Translation System - Architecture & Deployment

## Project Structure

```
translation-system/
├── core/
│   ├── config.py           # Environment & app config (Pydantic)
│   ├── database.py         # SQLAlchemy async engine, sessionmaker
│   ├── redis_client.py     # Redis connection pool & lifecycle
│   └── logging_config.py   # Structured logging (loguru/structlog)
│
├── db/
│   ├── models.py           # SQLAlchemy 2.0 ORM models
│   └── repositories.py     # Data access layer (Repository pattern)
│
├── schemas/
│   ├── enums.py            # JobStatus, SourceType
│   ├── translation.py      # Pydantic models for LLM I/O
│   ├── requests.py         # API request payloads
│   └── responses.py        # API response models
│
├── services/
│   ├── llm_pipeline.py     # Multi-agent orchestration (Translator → Stylist → QA)
│   ├── agents/
│   │   ├── base.py         # Abstract Agent class
│   │   ├── translator.py   # Translator agent
│   │   ├── stylist.py      # Stylist agent
│   │   └── quality_control.py  # QA agent with Pydantic structured output
│   ├── document_processor.py   # OCR, PDF/DOCX extraction
│   └── storage.py          # File upload/download (S3 or local)
│
├── api/
│   ├── main.py             # FastAPI app factory
│   ├── routes/
│   │   ├── translations.py  # Translation job endpoints
│   │   └── status.py        # Job status, results polling
│   └── dependencies.py     # Dependency injection
│
├── bot/
│   ├── main.py             # Aiogram dispatcher & setup
│   ├── handlers/
│   │   ├── start.py        # /start, help
│   │   ├── documents.py    # Document uploads, OCR dispatch
│   │   ├── text.py         # Direct text translation
│   │   └── status.py       # Job status polling
│   ├── middlewares.py      # Rate limiting, user validation
│   └── callbacks.py        # Inline buttons, query handlers
│
├── workers/
│   ├── celery_app.py       # Celery app instance & config
│   ├── tasks.py            # Celery task definitions
│   └── run.py              # Worker entry point
│
├── migrations/
│   └── alembic/            # Alembic DB migrations
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker/
│   ├── Dockerfile.api      # FastAPI
│   ├── Dockerfile.worker   # Celery worker
│   └── docker-compose.yml  # Local dev stack
│
├── pyproject.toml          # Poetry/pip dependencies
├── .env.example
└── main.py                 # CLI entry point


## Technology Stack

- **API Framework**: FastAPI (async)
- **Database**: PostgreSQL (via asyncpg/SQLAlchemy 2.0 Async)
- **Message Broker**: Redis (via aioredis)
- **Job Queue**: Celery (with async worker pool)
- **Bot Framework**: Aiogram 3.x (async Telegram bot)
- **LLM Providers**: OpenAI, Anthropic (Claude), Google Gemini via LiteLLM
- **Structured Output**: Pydantic V2 (JSON schema for LLM function calling)
- **Document Processing**: PyPDF2, python-docx, Tesseract (OCR)
- **Async HTTP**: httpx, aiohttp
- **Logging**: Loguru (structured, with context)
- **Validation**: Pydantic V2 with Field validators


## Deployment Patterns

### Local Development (docker-compose)
- FastAPI on http://localhost:8000
- Celery worker with Flower UI (monitoring)
- Redis (port 6379)
- PostgreSQL (port 5432)

### Production (Kubernetes / Docker)
- FastAPI pods (2-3 replicas)
- Celery worker fleet (auto-scaled based on queue length)
- Redis cluster (Sentinel for HA)
- PostgreSQL with streaming replication
- Telegram webhook (or polling fallback)

### Execution Flow

```
User (Telegram)
    ↓ (sends /start, document, text)
    ↓
Aiogram Bot Handler
    ↓ (validates, normalizes input)
    ↓
FastAPI POST /jobs
    ↓ (creates DB job, returns job_id)
    ↓
Celery Task Enqueue (process_translation_job.delay)
    ↓ (async, returns immediately)
    ↓
FastAPI returns job_id to Telegram
    ↓
User polls /jobs/{job_id}/status (or webhook callback)
    ↓
Celery Worker executes:
  1. Extract text (OCR if image/PDF)
  2. Run Translator agent → draft_translation
  3. Run Stylist agent → styled_translation
  4. Run QA agent → quality_report + final_translation
  5. Update DB job status → completed
    ↓
Telegram notifies user with result


## Data Flow & Error Handling

### Happy Path
pending → processing → translating → reviewing → completed

### Error Path  
pending → processing → failed (with retry_count < MAX_RETRIES)
→ pending (exponential backoff) → ...

### Timeout Handling
- FastAPI endpoint returns 202 Accepted (job_id) immediately
- Celery retries with exponential backoff (retry: default=True, max_retries=5)
- Quality report includes model_name, duration, token_count for observability
