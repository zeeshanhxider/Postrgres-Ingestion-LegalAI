# Parallel Processing Implementation

## Overview

The pipeline now supports parallel processing for both extraction and database insertion phases, significantly reducing total processing time.

## Changes Made

### 1. Parallel Batch Insertion (`pipeline/db_inserter.py`)

- `insert_batch()` now uses `ThreadPoolExecutor` to process multiple cases concurrently
- Each case's DB insertion and RAG processing runs in parallel
- Configurable via `--workers` flag (default: 4)

### 2. Duplicate Handling with Upsert

- Changed INSERT to use `ON CONFLICT (case_file_id, court_level) DO UPDATE`
- Re-running the pipeline updates existing cases instead of failing
- Related records (parties, judges, citations, etc.) are cleared and re-inserted on update

### 3. Race Condition Fixes (`pipeline/dimension_service.py`)

Added `ON CONFLICT DO UPDATE` to all dimension table inserts to prevent race conditions during parallel execution:

- `case_types` - `ON CONFLICT (case_type)`
- `stage_types` - `ON CONFLICT (stage_type)`
- `document_types` - `ON CONFLICT (document_type)`
- `courts_dim` - `ON CONFLICT (court)`

### 4. Database Constraint Fix

- Dropped partial unique index `idx_cases_unique_case_file`
- Created proper unique constraint: `cases_case_file_court_level_unique UNIQUE (case_file_id, court_level)`

### 5. Word Processor Bulk Insert Fix (`pipeline/word_processor.py`)

- Fixed SQLAlchemy 2.0 compatibility issue in `flush()` method
- Now uses proper parameterized bulk INSERT with uniquely named parameters
- Batches inserts in groups of 500 to avoid parameter limits

## What Runs in Parallel

1. **PDF Extraction** - Multiple PDFs extracted simultaneously
2. **LLM Extraction** - Multiple cases sent to Ollama concurrently
3. **DB Insertion + RAG** - Multiple cases inserted and RAG-processed concurrently

## Unchanged Functionality

- All data integrity preserved (each case in its own transaction)
- FK relationships properly maintained
- Full RAG processing (chunks, sentences, words, phrases, embeddings)
- Statute linking and auto-creation in `statutes_dim`

## Usage

```bash
# Run with 4 parallel workers (default)
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv downloads/Supreme_Court_Opinions/metadata.csv --workers 4 --pdf-extractor pdfplumber

# Reduce workers if Ollama server times out frequently
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv downloads/Supreme_Court_Opinions/metadata.csv --workers 2 --pdf-extractor pdfplumber
```

## Performance

- ~4x speedup with 4 workers compared to sequential processing
- Estimated ~20 hours for 4,330 PDFs with 4 workers (vs ~80 hours sequential)
