# Kotoback

A Django-based backend for intelligent book ingestion, NLP processing, and flashcard generation. Kotoback processes EPUB files, extracts vocabulary, applies linguistic filtering, translates content, and generates study flashcards with per-user customization. It is a remake of the original Kotoback I made during a programming bootcamp, in order to test out workflow optimizations and recreate the project in a new Techstack

## Overview

Kotoback is designed to help language learners create personalized flashcard decks from EPUB books. The system:

- **Ingests EPUB files** and extracts chapter text
- **Processes vocabulary** using advanced NLP techniques (tokenization, filtering, normalization)
- **Translates content** between languages via DeepL
- **Filters words** based on rarity profiles (e.g., top 2K, 4K, 6K common words)
- **Generates flashcards** with metadata and study tracking
- **Manages async jobs** using Celery + Redis for heavy lifting
- **Provides REST API** via Django REST Framework with camelCase JSON responses

### Key Features

- Multi-language support (English, Japanese, and extensible to others)
- Per-user bookcard management with study tracking
- Async EPUB ingestion with job progress tracking
- Intelligent word filtering (common words, newspaper kanji, rarity profiles)
- Automatic translation and normalization
- Comprehensive test coverage with integration tests

## Tech Stack

- **Framework**: Django 6.0 + Django REST Framework 3.16
- **Task Queue**: Celery 5.5 with Redis 7 broker
- **Database**: PostgreSQL 16 (or SQLite for development)
- **NLP**: spaCy, MeCab, custom tokenizers and filters
- **Translation**: DeepL API
- **File Processing**: BeautifulSoup4, lxml, custom EPUB parser
- **Documentation**: DeepL, Beautiful Soup
- **Testing**: unittests, integration tests

## API Overview

The API is rooted at `/api/` and primarily serves a React frontend with **camelCase JSON responses** and **snake_case request bodies**.

### Base URL
- Development: `http://localhost:8000/api/`
- All endpoints require authentication except where noted

### Authentication & Authorization

- Default permission: **Authenticated users only**
- Public endpoints explicitly opened:
  - `GET /api/home/` (with reduced data for anonymous users)
  - `GET /api/books/`
  - `GET /api/books/{id}/`

### API Endpoints

#### Homepage
```
GET /api/home/
```
- **Authenticated**: Returns current user's BookCards ordered by last_studied_at, then updated_at
- **Anonymous**: Returns `{ authenticated: false, bookcards: [] }`
- **Response**: List of bookcards with book summary and flashcard count

#### Books (Public, Read-Only)
```
GET /api/books/
GET /api/books/{id}/
```
- List all books in the system
- Retrieve book detail with default flashcards
- No authentication required

#### BookCards (Per-User)
```
GET    /api/bookcards/                    # List current user's bookcards
POST   /api/bookcards/                    # Create new bookcard
GET    /api/bookcards/{id}/               # Detail (user-scoped)
PATCH  /api/bookcards/{id}/               # Update
PUT    /api/bookcards/{id}/               # Replace
DELETE /api/bookcards/{id}/               # Delete
```
- All endpoints scoped to authenticated user
- Updates and creation set `updated_at` automatically

#### FlashCards (Nested under BookCards)
```
GET    /api/bookcards/{bookcardId}/flashcards/              # List
POST   /api/bookcards/{bookcardId}/flashcards/              # Create
GET    /api/bookcards/{bookcardId}/flashcards/{id}/         # Detail
PATCH  /api/bookcards/{bookcardId}/flashcards/{id}/         # Update
PUT    /api/bookcards/{bookcardId}/flashcards/{id}/         # Replace
DELETE /api/bookcards/{bookcardId}/flashcards/{id}/         # Delete
```
- Per-flashcard updates record study metadata
- Triggers `last_studied_at` update on parent BookCard

#### Ingestion Jobs (EPUB Upload & Processing)
```
POST   /api/ingestion-jobs/                               # Upload EPUB
GET    /api/ingestion-jobs/{jobId}/                        # Check status
GET    /api/ingestion-jobs/{jobId}/result/                 # Fetch results
POST   /api/ingestion-jobs/{jobId}/cancel/                 # Cancel job
```
See [EPUB Upload with Celery/Redis](#epub-upload-with-celeryredis) for details.

### JSON Format

**Outgoing (Response)**: camelCase
```json
{
  "id": 1,
  "lastStudiedAt": "2026-04-06T10:30:00Z",
  "bookcard": { "id": 1, "fronLanguage": "en" }
}
```

**Incoming (Request)**: snake_case (current default)
```json
{
  "source_language": "en",
  "target_language": "ja",
  "card_count_target": 500
}
```

## EPUB Upload with Celery/Redis

The EPUB ingestion pipeline is orchestrated asynchronously to handle large files and complex NLP processing without blocking the HTTP server.

### Architecture

```
┌─────────────────┐
│  User uploads   │
│  EPUB via API   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│  Create IngestionJob     │
│  Return job_id           │
│  (Immediate HTTP 202)    │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Redis (Celery Broker)   │
│  Queue ingestion task    │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Celery Worker           │
│  Processes EPUB pipeline │
│  Updates job status      │
└──────────────────────────┘
         │
         ├─→ Extract spine/chapters
         ├─→ Tokenize text
         ├─→ Filter candidates
         ├─→ Translate words
         ├─→ Create flashcards
         │
         ▼
┌──────────────────────────┐
│  IngestionJob marked     │
│  COMPLETED or FAILED     │
│  Results in job.result   │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│  User polls GET result   │
│  or retrieves via API    │
└──────────────────────────┘
```

### Job Request Schema

**POST** `/api/ingestion-jobs/`

```python
{
  "source_language": str,           # "en", "ja", etc.
  "target_language": str,           # "en", "ja", etc.
  "card_count_target": int,         # Target number of cards
  "rarity_profile": {
    "filter_class": str,            # "common_english" | "common_japanese"
    "common_words": str,            # "2k" | "4k" | "6k" | "8k" | "10k"
    "include_newspaper_kanji": bool # Only for Japanese
  }
}
```

### Processing Pipeline Stages

Celery executes a series of stages, updating the job progress at each checkpoint:

| Stage | Progress | Task |
|-------|----------|------|
| `starting` | 5% | Initialize job |
| `extracting-spine` | 20% | Parse EPUB, extract chapter paths from manifest |
| `extracting-text` | 30-70% | Read and extract text from each chapter |
| `tokenizing` | 70% | Split text into half-candidates (morphemes/words) |
| `filtering` | 75% | Apply rarity filters (common words, kanji) |
| `translating` | 80-95% | Batch translate via DeepL |
| `finalizing` | 95-99% | Create FlashCard records in bulk |
| `completed` | 100% | Success |

### Job Status Endpoints

**GET** `/api/ingestion-jobs/{jobId}/`
```json
{
  "id": 42,
  "status": "PROCESSING",
  "currentStage": "translating",
  "progress": 87,
  "cardCountTarget": 500,
  "cardCountActual": 437,
  "errorMessage": null
}
```

**Status Values**: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`

**GET** `/api/ingestion-jobs/{jobId}/result/`
```json
{
  "status": "COMPLETED",
  "bookcardId": 12,
  "flashcardsCreated": 437,
  "cardCounts": {
    "before": 0,
    "after": 437
  }
}
```

**POST** `/api/ingestion-jobs/{jobId}/cancel/`
- Marks job `CANCELLED` at next stage checkpoint
- Avoids killing mid-transaction; gracefully halts on completion of current stage

### Celery Configuration

**Broker**: Redis (default `redis://localhost:6379/0`)
**Result Backend**: Configured via settings, typically Redis too

**Scheduled Tasks** (via Celery Beat):
- `2 AM daily`: Cleanup old (>7 days) ingestion jobs
- `3 AM daily`: Cleanup orphaned EPUB files without associated jobs

**Task Routing**: All ingestion tasks auto-discovered and registered in `book.tasks`.

### Development: Running Services

#### Using Docker Compose

```bash
docker-compose up
```

Services:
- **Web**: Django dev server on `http://localhost:8000`
- **Redis**: Broker on `localhost:6379`
- **PostgreSQL**: Database on `localhost:5433`

#### Manual Setup (Local Development)

```bash
# 1. Start Redis (macOS with Homebrew)
brew services start redis

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Start Django development server
cd Kotoback
python manage.py runserver

# 4. In a new terminal, start Celery worker
source .venv/bin/activate
cd Kotoback
celery -A Kotoback worker --loglevel=info

# 5. (Optional) Start Celery Beat for scheduled tasks
celery -A Kotoback beat --loglevel=info
```

### File Storage

- **Media Root**: `Kotoback/media/` (development) or `/app/media` (Docker)
- **EPUB files**: Stored in `media/ingestion-jobs/{year}/` with UUID-based names
- **Cleanup**: Old files are purged by the scheduled cleanup task

## Project Structure

```
Kotoback/
├── manage.py                 # Django admin CLI
├── requirements.txt          # Python dependencies
├── db.sqlite3               # Development database (if using SQLite)
├── Dockerfile               # Container image definition
│
├── Kotoback/                # Project settings & config
│   ├── settings.py          # Django settings (DB, Celery, REST_FRAMEWORK)
│   ├── urls.py              # Root URL routing
│   ├── celery.py            # Celery app + Beat schedule
│   ├── asgi.py              # ASGI config
│   └── wsgi.py              # WSGI config
│
├── book/                    # Main app (models, views, tasks)
│   ├── models.py            # Book, BookCard, FlashCard, IngestionJob
│   ├── views.py             # API views (homepage, books, cards, jobs)
│   ├── serializers.py       # DRF serializers
│   ├── urls.py              # API endpoints
│   ├── tasks.py             # Celery task definitions
│   ├── admin.py             # Django admin registration
│   ├── apps.py              # App configuration
│   │
│   ├── nlp/                 # NLP processing, tokenization, filtering
│   │   ├── extract.py       # EPUB chapter extraction
│   │   ├── tokenize.py      # Morphological analysis
│   │   ├── filters.py       # Word rarity filtering
│   │   ├── normalize_en.py  # English text normalization
│   │   ├── normalize_ja.py  # Japanese text normalization
│   │   ├── types.py         # Data types (Candidate, WordFilterSelection)
│   │   ├── rarity.py        # Word frequency lists
│   │   └── word_filters/    # Language-specific filter definitions
│   │
│   ├── migrations/          # Database schema versions
│   ├── tests/               # Comprehensive test suite
│   │   ├── integration_tests/      # Full EPUB pipeline tests
│   │   ├── jobs/                   # Task tests
│   │   ├── models_views/           # API endpoint tests
│   │   └── nlp/                    # NLP component tests
│   │
│   ├── data/                # Sample/fixture data
│   └── translations/        # Language translation exceptions
│
├── study/                   # Study tracking app (placeholder)
├── utils/                   # Shared utilities
│   ├── renderers.py         # CamelCase JSON renderer
│   └── serializers.py       # Common serializer mixins
│
└── media/                   # Uploaded files & processing artifacts
```

## Running Tests



### Run All Tests

If not running tests in docker, remove `docker-compose exec web` from the command

```bash
docker-compose exec web python manage.py test
```

### Run Tests with Verbose Output

```bash
# Verbosity 2 (medium detail)
docker-compose exec web python manage.py test --verbosity=2

# Verbosity 3 (full detail - includes test names)
docker-compose exec web python manage.py test -v 3

# Keep Quiet (only failures shown)
docker-compose exec web python manage.py test --verbosity=0
```

### Run All Tests in a Single App

```bash
# All book tests
docker-compose exec web python manage.py test book

# All study tests
docker-compose exec web python manage.py test study
```

### Run Tests in a Specific Module/Folder

```bash
# All NLP extraction tests
docker-compose exec web python manage.py test book.nlp.tests.test_extract_spine

# All filters tests
docker-compose exec web python manage.py test book.nlp.tests.test_filters

# All tokenize tests
docker-compose exec web python manage.py test book.nlp.tests.test_tokenize
```

### Run a Single Test Class

```bash
# BookCard API tests
docker-compose exec web python manage.py test book.test_bookcard_api.BookCardApiTests

# FlashCard API tests
docker-compose exec web python manage.py test book.test_flashcard_api.FlashCardApiTests

# Extraction spine tests
docker-compose exec web python manage.py test book.nlp.tests.test_extract_spine.ExtractSpineTests
```


## Environment Variables

See `docker-compose.yml` for full list. Key vars:

```bash
DJANGO_SECRET_KEY            # Secret key for crypto (required in production)
DJANGO_DEBUG                 # 1 for dev, 0 for production
DJANGO_ALLOWED_HOSTS         # Comma-separated domain list
POSTGRES_DB                  # Database name
POSTGRES_USER                # Database user
POSTGRES_PASSWORD            # Database password
POSTGRES_HOST                # Database host (postgres in Docker)
USE_SQLITE                   # 1 to use SQLite instead of Postgres
CELERY_BROKER_URL            # Redis broker URL
MEDIA_ROOT                   # Path to media files
```

## Development Workflow

### Setting Up for Development

```bash
# Clone and install
git clone <repo>
python -m venv .venv
source .venv/bin/activate
cd Kotoback
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start services
docker-compose up           # Redis + Postgres in containers
python manage.py runserver  # Django dev server
celery -A Kotoback worker   # Celery worker (in another terminal)
```


## Design Decisions

### JSON Casing

- **Outgoing responses**: camelCase (future: `CamelCaseJSONRenderer`)
- **Model fields & serializers**: snake_case in Python
- **Incoming requests**: camelCase (via `CamelCaseInputMixin`)

### Authentication

- Uses Django + DRF TokenAuthentication
- `IsAuthenticated` as default permission class
- Public endpoints explicitly listed in permission classes

### BookCard Study Tracking

- `last_studied_at` updates when any FlashCard is modified
- Homepage sorts by `last_studied_at` (desc), then `updated_at` (desc)
- Provides heuristic for "recently studied" ordering

## Future Topics

- [ ] support Text, PDF formats in addition to EPUB
- [ ] error handling for DRM EPUB uploads
- [ ] Let the frontend determine last_studied_at value

## Support & Troubleshooting

### EPUB Processing Fails

- Check logs: `Celery worker terminal`
- Possible issues:
  - EPUB file corrupt or unsupported format
  - DeepL API rate limit or invalid API key
