# Legal Case Ingestion Pipeline

Production-grade pipeline for extracting structured data from Washington State court opinion PDFs and populating a PostgreSQL database with full RAG (Retrieval-Augmented Generation) support.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PDF Input                                       │
│                    (Court opinions from downloads/)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PDFExtractor                                       │
│              LlamaParse API (primary) + pdfplumber (fallback)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLMExtractor                                       │
│                    Ollama qwen:32b structured extraction                     │
│     Extracts: parties, judges, attorneys, citations, statutes, issues       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CaseProcessor                                       │
│              Orchestrates PDF → LLM → ExtractedCase model                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DatabaseInserter                                     │
│                   Inserts case + related entities                            │
│            Uses DimensionService for FK resolution                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAGProcessor                                        │
│                                                                              │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   Chunker    │  │ SentenceProcessor │  │WordProcessor │  │  Phrase    │ │
│  │ (350 words)  │→ │ (citation-aware)  │→ │ (dictionary) │  │ Extractor  │ │
│  └──────────────┘  └───────────────────┘  └──────────────┘  └────────────┘ │
│                                                                              │
│  Configurable: chunk_embedding_mode, phrase_filter_mode                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL + pgvector                                │
│                                                                              │
│  cases ─┬─► parties        case_chunks ─► case_sentences ─► word_occurrence │
│         ├─► case_judges    case_phrases   word_dictionary                   │
│         ├─► attorneys      embeddings (1024-dim vectors)                    │
│         ├─► citation_edges                                                  │
│         ├─► statute_citations                                               │
│         └─► issues_decisions                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

| File                    | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `config.py`             | Environment configuration (DB, Ollama, LlamaParse)   |
| `models.py`             | Data models: `ExtractedCase`, `Party`, `Judge`, etc. |
| `pdf_extractor.py`      | PDF to text using LlamaParse + pdfplumber fallback   |
| `llm_extractor.py`      | Structured extraction using Ollama LLM               |
| `case_processor.py`     | Orchestrates extraction pipeline                     |
| `db_inserter.py`        | Database insertion with RAG integration              |
| `dimension_service.py`  | FK resolution for dimension tables                   |
| `chunker.py`            | Section-aware text chunking                          |
| `sentence_processor.py` | Sentence extraction with citation protection         |
| `word_processor.py`     | Word dictionary and occurrence tracking              |
| `phrase_extractor.py`   | Legal phrase n-gram extraction                       |
| `rag_processor.py`      | Main RAG orchestrator                                |

## Usage

### Quick Start Examples

```bash
# Process 1 Court of Appeals Published cases with metadata
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published --csv downloads/Court_of_Appeals_Published/metadata.csv --limit 1 --workers 1 --pdf-extractor pdfplumber

# Process 10 Supreme Court opinions
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv downloads/Supreme_Court_Opinions/metadata.csv --limit 10 --workers 1 --pdf-extractor pdfplumber

# Process 100 cases with 4 parallel workers
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published --csv downloads/Court_of_Appeals_Published/metadata.csv --limit 100 --workers 4 --pdf-extractor pdfplumber
```

### Process a Single Case

```bash
python -m pipeline.run_pipeline --pdf downloads/Supreme_Court_Opinions/2025/January/case.pdf --csv downloads/Supreme_Court_Opinions/metadata.csv --row 21
```

### Batch Processing

```bash
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv downloads/Supreme_Court_Opinions/metadata.csv --limit 50
```

### Parallel Processing

Process multiple cases concurrently for faster batch ingestion:

```bash
# Process with 4 workers (default)
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published/2024 --csv downloads/Court_of_Appeals_Published/metadata.csv --workers 4

# Process with 8 workers
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published/2024 --csv downloads/Court_of_Appeals_Published/metadata.csv --workers 8

# Force sequential processing (1 at a time)
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published/2024 --csv downloads/Court_of_Appeals_Published/metadata.csv --sequential
```

**Note:** Parallel processing significantly speeds up batch ingestion but may hit rate limits on LlamaParse or Ollama servers. Adjust `--workers` based on your server capacity.

### PDF Extraction Options

Choose PDF extraction method:

```bash
# Use pdfplumber (default, faster, more reliable)
python -m pipeline.run_pipeline --pdf case.pdf --pdf-extractor pdfplumber

# Use LlamaParse (better OCR, requires API key)
python -m pipeline.run_pipeline --pdf case.pdf --pdf-extractor llamaparse

# Auto mode (tries LlamaParse first, falls back to pdfplumber)
python -m pipeline.run_pipeline --pdf case.pdf --pdf-extractor auto
```

**Recommendation:** Use `pdfplumber` for Washington State court opinions (clean PDFs). Use `llamaparse` for scanned documents or complex layouts.

### RAG Options

```bash
# Chunk embedding modes
--chunk-embedding all        # Embed all chunks (default)
--chunk-embedding important  # Only ANALYSIS, FACTS, HOLDING sections
--chunk-embedding none       # Skip chunk embeddings

# Phrase filtering modes
--phrase-filter strict       # Only legal terminology (default)
--phrase-filter relaxed      # All meaningful phrases

# Skip RAG entirely
--no-rag
```

### Verify a Case

```bash
python -m pipeline.run_pipeline --verify --case-id 21
```

### Extract Only (No Database)

```bash
python -m pipeline.run_pipeline --pdf case.pdf --no-rag
```

### Additional Options

```bash
# Limit number of files to process in batch
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published/2024 --limit 10

# Verbose logging
python -m pipeline.run_pipeline --pdf case.pdf --verbose

# Combine multiple options
python -m pipeline.run_pipeline --batch --pdf-dir downloads/Court_of_Appeals_Published/2024 --csv downloads/Court_of_Appeals_Published/metadata.csv --workers 8 --limit 100 --pdf-extractor pdfplumber --chunk-embeddings all --phrase-filter strict
```

## Command-Line Arguments

| Argument             | Type   | Default    | Description                                |
| -------------------- | ------ | ---------- | ------------------------------------------ |
| `--batch`            | flag   | False      | Enable batch processing mode               |
| `--pdf`              | string | None       | Path to single PDF file                    |
| `--pdf-dir`          | string | None       | Directory with PDF files (for batch)       |
| `--csv`              | string | None       | Path to metadata CSV file                  |
| `--row`              | int    | None       | Row number in CSV (1-indexed, single mode) |
| `--limit`            | int    | None       | Max files to process in batch              |
| `--workers`          | int    | 4          | Number of parallel workers                 |
| `--sequential`       | flag   | False      | Disable parallel processing                |
| `--pdf-extractor`    | choice | pdfplumber | `llamaparse`, `pdfplumber`, or `auto`      |
| `--enable-rag`       | flag   | True       | Enable RAG processing (default)            |
| `--no-rag`           | flag   | False      | Disable RAG processing                     |
| `--chunk-embeddings` | choice | all        | `all`, `important`, or `none`              |
| `--phrase-filter`    | choice | strict     | `strict` or `relaxed`                      |
| `--verify`           | flag   | False      | Verify case data in database               |
| `--case-id`          | int    | None       | Case ID for verification                   |

## Quality Assurance & Data Verification

### QA Export Tool

Export case data for quality assurance and comparison against manual standards:

```bash
# Generate QA summary report with metrics
python -m pipeline.qa_export --report --output logs/qa_report.json

# Export cases to CSV for manual review
python -m pipeline.qa_export --output logs/qa_review.csv --limit 100

# Export to Excel with formatting
python -m pipeline.qa_export --output logs/qa_review.xlsx --format excel --limit 50

# Export specific cases
python -m pipeline.qa_export --case-ids 1,2,3,4,5 --output logs/specific_cases.csv
```

**QA Report Includes:**

- Total cases and issue counts
- Issue count distribution (identifies single-issue cases)
- Outcome distribution (Affirmed, Reversed, Remanded, Dismissed, Mixed)
- Winner role distribution
- Data quality flags (% single-issue cases, % cases without issues)

**CSV Export Format:**

- Flattened structure for easy comparison with Excel standards
- Up to 5 issues per case with separate columns
- Party and judge lists
- RCW count, citation count, statute count
- Extraction timestamp for traceability

### Data Quality Checks

The pipeline enforces:

1. **Issue Outcome Standardization**: Only 5 valid values (Affirmed, Dismissed, Reversed, Remanded, Mixed)
2. **Winner Role Validation**: Prevents outcome values (e.g., "Affirmed") in winner_legal_role field
3. **RCW Dimension**: Normalized RCW citations in `rcw_dim` table for rollup queries
4. **Multi-Issue Extraction**: LLM prompt explicitly instructs extraction of 2-5 distinct issues per case

### QA View

Query the `v_qa_extraction` view for quick data quality checks:

```sql
-- Check cases with potential quality issues
SELECT case_id, title, issue_count, overall_outcome
FROM v_qa_extraction
WHERE issue_count <= 1
ORDER BY case_id DESC
LIMIT 20;

-- RCW rollup by title
SELECT r.title, r.chapter, COUNT(*) as usage_count
FROM rcw_dim r
JOIN issue_rcw ir ON r.rcw_id = ir.rcw_id
GROUP BY r.title, r.chapter
ORDER BY usage_count DESC;
```

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5435/cases_llama3_3

# Ollama LLM
OLLAMA_BASE_URL=https://ollama.legaldb.ai
OLLAMA_MODEL=qwen:32b
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large

# LlamaParse (PDF OCR)
LLAMA_CLOUD_API_KEY=llx-...
```

## Database Tables Populated

**Core Tables:**

- `cases` - Main case record with full text and embedding
- `parties` - Plaintiff, defendant, appellant, respondent
- `case_judges` - Judges linked via `judges` table
- `attorneys` - Legal representation
- `citation_edges` - Case citations
- `statute_citations` - Statutory references
- `issues_decisions` - Legal issues and outcomes
- `rcw_dim` - Normalized RCW statutes (NEW)
- `issue_rcw` - Junction table linking issues to RCWs (NEW)

**RAG Tables:**

- `case_chunks` - Text chunks with section type and optional embedding
- `case_sentences` - Sentences within chunks
- `word_dictionary` - Unique words across corpus
- `word_occurrence` - Word positions in sentences
- `case_phrases` - Extracted legal phrases (2-4 grams)

**Dimension Tables:**

- `courts_dim` - Court information (resolved to `court_id`)
- `case_types` - Case type taxonomy
- `stage_types` - Procedural stage taxonomy

## Example Output

```
Processing: 102586-6.pdf
  Metadata: 102,586-6 - Pub. Util. Dist. No. 1 v. State
  Extracted 28547 chars from 12 pages
  Running LLM extraction...
  Extraction complete: 4 parties, 10 judges, 3 issues
✓ Inserted as case_id: 21
  RAG: 15 chunks, 142 sentences, 2847 words, 89 phrases
```
