# Docker Commands for Development

## Restart Docker and Run Migrations

### Option 1: Step-by-step (Recommended for clarity)

```bash
# Stop and remove all containers
docker-compose down

# Build images (if Dockerfile changed)
docker-compose build

# Start containers in background
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate
```

### Option 2: One-liner

```bash
docker-compose down && docker-compose up -d && docker-compose exec web python manage.py migrate
```

---

## Command Breakdown

| Command | Purpose |
|---------|---------|
| `docker-compose down` | Stop and remove all containers defined in docker-compose.yml |
| `docker-compose build` | Rebuild Docker images (only needed if Dockerfile changed) |
| `docker-compose up -d` | Start containers in background (`-d` = detached mode) |
| `docker-compose exec web` | Execute a command inside the running `web` container |
| `python manage.py migrate` | Apply Django migrations to the database |

---

## Important Notes

- **Service Name**: Replace `web` with your actual service name from `docker-compose.yml`
  - Common alternatives: `django`, `app`, `backend`, `kotoback`
  - To find it: `cat docker-compose.yml | grep "^  [a-z]"`

- **Viewing Logs**: Omit `-d` flag to see real-time logs:
  ```bash
  docker-compose up  # Shows logs in terminal
  ```

- **Skip Build**: If only Python code changed (not Dockerfile):
  ```bash
  docker-compose down && docker-compose up -d && docker-compose exec web python manage.py migrate
  ```

- **No Downtime**: To avoid stopping containers:
  ```bash
  docker-compose exec web python manage.py migrate
  ```
  (Only if containers are already running)

---

## Verify Migrations

After running migrations, verify they applied:

```bash
docker-compose exec web python manage.py showmigrations book
```

Should show bookcard title, author, epub_id as `[X]` (applied).

---

## Running Tests in Docker

### Run All Tests

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

### Run a Single Test Method

```bash
# Single BookCard test
docker-compose exec web python manage.py test book.test_bookcard_api.BookCardApiTests.test_homepage_anonymous_empty

# Single extraction test
docker-compose exec web python manage.py test book.nlp.tests.test_extract_spine.ExtractSpineTests.test_get_rootfile_path_from_epub_top_level_opf

# Single finalization test
docker-compose exec web python manage.py test book.test_task_finalization.IngestionTaskFinalizationTests.test_finalize_creates_multiple_flashcards
```

### Run Multiple Test Modules in One Command

```bash
# Book API tests together
docker-compose exec web python manage.py test book.test_bookcard_api book.test_flashcard_api

# All ingestion tests
docker-compose exec web python manage.py test book.test_ingestion_api book.test_ingestion_serializers

# All NLP tests
docker-compose exec web python manage.py test book.nlp.tests.test_extract_spine book.nlp.tests.test_extract_metadata book.nlp.tests.test_filters book.nlp.tests.test_tokenize
```

### Useful Test Flags

```bash
# Stop on first failure (useful for quick feedback)
docker-compose exec web python manage.py test --failfast

# Combine verbosity + failfast
docker-compose exec web python manage.py test -v 2 --failfast

# Keep test database after run (for inspection)
docker-compose exec web python manage.py test --keepdb

# Run tests in parallel (faster)
docker-compose exec web python manage.py test --parallel

# Run with coverage report (requires coverage package)
docker-compose exec web coverage run --source='.' manage.py test && docker-compose exec web coverage report
```

### Testing Workflow Example

```bash
# 1. Restart Docker with fresh migrations
docker-compose down && docker-compose up -d && docker-compose exec web python manage.py migrate

# 2. Run all tests to verify baseline
docker-compose exec web python manage.py test -v 2

# 3. Run specific test while developing
docker-compose exec web python manage.py test book.test_bookcard_api --failfast -v 2

# 4. Run full test suite before committing
docker-compose exec web python manage.py test --failfast
```

---

## Quick Reference

```bash
# Full restart with build
docker-compose down && docker-compose build && docker-compose up -d && docker-compose exec web python manage.py migrate

# Restart without rebuild
docker-compose down && docker-compose up -d && docker-compose exec web python manage.py migrate

# Just run migrations (if already running)
docker-compose exec web python manage.py migrate

# Run all tests
docker-compose exec web python manage.py test

# Run tests with verbose output + failfast
docker-compose exec web python manage.py test -v 2 --failfast

# Run single test file
docker-compose exec web python manage.py test book.test_bookcard_api

# Run single test method
docker-compose exec web python manage.py test book.test_bookcard_api.BookCardApiTests.test_homepage_anonymous_empty

# View running containers
docker-compose ps

# View logs
docker-compose logs -f web

# Stop all containers
docker-compose down
```
