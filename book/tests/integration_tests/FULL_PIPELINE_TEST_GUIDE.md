# Full Pipeline Integration Test Guide

## Overview

`test_full_pipeline.py` validates the **complete EPUB ingestion pipeline**—not just the API contract, but actual pipeline execution from upload through flashcard creation.

### Test Coverage

The test suite includes three comprehensive scenarios:

1. **`test_upload_english_epub_creates_flashcards_pipeline_end_to_end`**
   - Uploads real English EPUB
   - Verifies: job SUCCEEDED, flashcards created with correct language pair
   - Mocks: `translate_base_words()` to avoid DeepL API call

2. **`test_japanese_epub_pipeline_succeeds`**
   - Uploads real Japanese EPUB
   - Verifies: Japanese tokenization (spaCy + MeCab) → flashcards

3. **`test_user_scope_enforced_on_pipeline_results`**
   - Uploads EPUB as user 1
   - Attempts access as user 2
   - Verifies: user 2 gets 404 (permission boundary enforced)

## Setup: What You Need to Provide

### 1. Real EPUB Files

The tests skip gracefully if EPUB files aren't present, but they won't run full validation. You must add:

- **`book/tests/integration_tests/data/test-en.epub`**
  - Any valid EPUB with English prose (e.g., a chapter from a book, Wikipedia content, etc.)
  - Minimum: 2–3 paragraphs of English text
  - Can grab free EPUBs from: Project Gutenberg, Standard Ebooks, etc.

- **`book/tests/integration_tests/data/test-ja.epub`** (optional)
  - Valid EPUB with Japanese text (2–3 paragraphs)
  - If missing: `test_japanese_epub_pipeline_succeeds` skips
  - Japanese test validates fugashi + MeCab tokenization

### 2. Ensure Docker Services Running

The tests assume your local dev environment works with `docker-compose.yml`.

```bash
# From Kotoback/ directory
docker-compose up -d redis postgres
```

This starts:
- PostgreSQL (stores jobs, flashcards, users)
- Redis (broker for Celery)

### 3. Ensure Dependencies Installed

The tests require spaCy and fugashi models pre-downloaded.

```bash
# From Kotoback/ directory
pip install -e .  # or: pip install -r requirements.txt

# Download spaCy English model (used during ingestion)
python -m spacy download en_core_web_sm

# Download MeCab dictionary (used for Japanese tokenization)
# Already handled by fugashi; verify with:
python -c "import fugashi; print('fugashi OK')"
```

## Running the Tests

### Full Pipeline Tests Only (Recommended: Run from Docker Container)

Since these integration tests depend on PostgreSQL and Redis, running from the web container ensures proper networking and avoids local dependency issues.

```bash
# From project root (cursor_made/ directory)
docker-compose exec web python manage.py test book.tests.integration_tests.test_full_pipeline -v 2
```

**Expected output:**
```
test_upload_english_epub_creates_flashcards_pipeline_end_to_end (book.tests.integration_tests.test_full_pipeline.FullPipelineIntegrationTest) ... ok
test_japanese_epub_pipeline_succeeds (book.tests.integration_tests.test_full_pipeline.FullPipelineIntegrationTest) ... SKIPPED
test_user_scope_enforced_on_pipeline_results (book.tests.integration_tests.test_full_pipeline.FullPipelineIntegrationTest) ... ok
```

(Japanese test skips if `test-ja.epub` not present.)

### Alternative: Run Locally (if all dependencies installed)

```bash
# From Kotoback/ directory
python manage.py test book.tests.integration_tests.test_full_pipeline -v 2
```

Note: Local execution requires spaCy models and database/Redis connectivity via settings.py.

### Run All Integration Tests

```bash
# API contract tests + full pipeline tests (from container)
docker-compose exec web python manage.py test book.tests.integration_tests -v 2
```

## What These Tests Validate

✅ **API Contract**
- Upload endpoint returns 201 with job_id
- Status endpoint enforces user scope

✅ **Task Execution (Eager Mode)**
- Celery task runs synchronously
- Job transitions QUEUED → PROCESSING → SUCCEEDED

✅ **EPUB Extraction**
- EPUB spinefile parsed correctly
- Text extracted from chapters

✅ **Tokenization & Ranking**
- English: spaCy tokenization + rarity ranking
- Japanese: fugashi tokenization + MeCab + rarity ranking

✅ **Translation Integration**
- Mocked `translate_base_words()` called with correct candidates
- Translations stored in flashcard data

✅ **Flashcard Creation**
- BookCard created and linked to job
- FlashCard objects created with correct language pair
- Cards have `front_data` (English word + POS) + back translation

✅ **User Scope**
- Job belongs to uploading user
- Other users get 404 on status/result endpoints

## Troubleshooting

### Test Skipped: "Test EPUB not found"

**Cause:** EPUB files not in `book/tests/integration_tests/data/`

**Solution:**
```bash
# Add your EPUB files
cp ~/Downloads/sample-ebook.epub Kotoback/book/tests/integration_tests/data/test-en.epub
```

### Error: "E050: Can't find model 'en_core_web_sm'"

**Cause:** spaCy model not downloaded

**Solution:**
```bash
python -m spacy download en_core_web_sm
```

### Error: "Error: No space not found"

**Cause:** MeCab/fugashi not properly installed (Japanese only)

**Solution:**
```bash
# Verify fugashi can initialize MeCab
python -c "import fugashi; tagger = fugashi.Tagger(); print(tagger('テスト'))"
```

### Job Status: "FAILED" (unexpected)

**Check error payload:**
```python
# In a shell
python manage.py shell
from book.models import IngestionJob
job = IngestionJob.objects.latest('created_at')
print(job.error_payload)
```

Common issues:
- EPUB file corrupted or invalid Zip structure
- Language not recognized (must be `en` or `ja`)
- Translation mock not applied correctly

## How the Tests Work: Technical Details

### Celery Eager Mode

Tests use `@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)`.

This makes Celery execute tasks **synchronously** in the test process, avoiding the need to:
- Start a separate worker process
- Wait for task completion
- Mock complex async result objects

### TransactionTestCase

Uses database transactions to isolate test data:
- Each test starts fresh
- Writes to real database (not mocked)
- Validates actual ORM behavior

### Mocking Strategy

Only **one** function is mocked: `translate_base_words()` (calls DeepL API).

Everything else runs real:
- EPUB extraction via ZipFile + lxml
- Tokenization via spaCy/fugashi
- Word ranking via frequency filters
- Database writes via Django ORM

This ensures the pipeline is genuinely validated, not just the mock structure.

---

## Success Criteria

### ✅ All Tests Pass

```
Ran 3 tests in 45.231s
OK
```

**Indicates:**
- EPUB extraction working
- Tokenization/ranking working
- Translation mocking working
- Flashcard creation working
- User scope boundary enforced

### What You Get

After running successfully, you'll have:

📊 **Confidence** that the ingestion pipeline works end-to-end
🛡️ **Permission validation** that user scope boundaries are enforced
📈 **Reusable test framework** for future pipeline changes

### Next Steps After Tests Pass

1. **Frontend Development** — Create UI to upload EPUBs + display flashcards
2. **Performance Tuning** — Optimize extraction for large EPUBs (profile with real data)
3. **Observability** — Add logging/metrics to track job execution across worker processes
4. **Production Deployment** — Use test framework to validate Celery + Redis in staging

---

## Q&A

**Q: Can I run these tests without Docker?**
A: Yes, if PostgreSQL + Redis are already running elsewhere. Tests connect via `DATABASES` and `CELERY_BROKER_URL` in `settings.py`.

**Q: Can I use synthetic EPUBs instead of real files?**
A: Yes! The `EPUBFactory` from `epub_factory.py` can generate minimal test EPUBs. Just update test imports to use it.

**Q: Do I need to run the worker process?**
A: No. Eager mode executes tasks synchronously during the upload request itself.

**Q: Why mock DeepL when everything else is real?**
A: DeepL requires API credentials and rate-limiting. Mocking it keeps tests fast, reliable, and credential-free while still validating the integration points.
