# System Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Core Components](#core-components)
5. [Data Flow](#data-flow)
6. [Database Schema](#database-schema)
7. [API Architecture](#api-architecture)
8. [AI/ML Pipeline](#aiml-pipeline)
9. [Deployment Architecture](#deployment-architecture)
10. [Directory Structure](#directory-structure)

---

## Overview

**Law Helper** is a comprehensive legal document processing system designed for Washington State family law appellate cases. It combines AI-powered extraction, Retrieval-Augmented Generation (RAG) capabilities, and advanced search functionalities to process and analyze legal documents.

### Key Capabilities

- **AI-Powered Extraction**: Automated extraction of legal entities using Ollama/OpenAI
- **RAG System**: Vector embeddings and semantic search for legal documents
- **Hybrid Search**: Combines semantic search (embeddings), lexical search (word positions), and phrase matching
- **Washington State Specialization**: Specialized categorization for divorce appeals cases
- **REST API**: FastAPI-based interface for all operations
- **Batch Processing**: Bulk PDF processing with comprehensive metadata extraction

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  (REST API Clients, Web UI, Batch Processors)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     FASTAPI APPLICATION                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Navigation  │  │    Batch     │  │    Cases     │         │
│  │  Endpoints   │  │  Processing  │  │  Management  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     SERVICE LAYER                                │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Case Ingestor (Orchestration)                      │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│        │
│  │  │    AI    │ │ Database │ │   Word   │ │ Phrase ││        │
│  │  │Extractor │ │ Inserter │ │Processor │ │Extract.││        │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘│        │
│  └─────────────────────────────────────────────────────┘        │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Supporting Services                                 │        │
│  │  • Embedding Service (Ollama)                       │        │
│  │  • Context Navigator (Word-to-Document)             │        │
│  │  • Dimension Service (Lookup Tables)                │        │
│  │  • Sentence Processor, PDF Parser, Text Chunker     │        │
│  └─────────────────────────────────────────────────────┘        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     DATA LAYER                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐   │
│  │   PostgreSQL     │  │      Redis       │  │  Ollama    │   │
│  │   (pgvector)     │  │   (Caching)      │  │  (Local)   │   │
│  └──────────────────┘  └──────────────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
PDF Upload → PDF Parser → AI Extractor → Database Inserter
                    ↓                           ↓
              Text Chunker                  Dimension Service
                    ↓                           ↓
           Sentence Processor          Case/Parties/Attorneys
                    ↓                      Judges/Issues
            Word Processor              Citations/Arguments
                    ↓                           ↓
            Phrase Extractor            ┌──────────────┐
                    ↓                   │  PostgreSQL  │
            Embedding Service           │   Database   │
                    ↓                   └──────────────┘
            Vector Storage
```

---

## Technology Stack

### Backend

- **Framework**: FastAPI 0.104+ (async Python web framework)
- **Language**: Python 3.11+
- **ORM**: SQLAlchemy 2.0+ (raw SQL for performance-critical operations)
- **Validation**: Pydantic 2.0+ (data validation and serialization)

### Database

- **Primary Database**: PostgreSQL 16 with pgvector extension
- **Extensions**:
  - `pgvector` - Vector similarity search (1024-dimensional embeddings)
  - `pg_trgm` - Trigram matching for fuzzy search
  - `citext` - Case-insensitive text
  - `unaccent` - Accent-insensitive search
  - `pgcrypto` - UUID generation

### AI/ML

- **Local LLM**: Ollama (qwen:32b for extraction, mxbai-embed-large for embeddings)
- **Cloud LLM**: OpenAI GPT-4o-mini (fallback)
- **Embedding Dimension**: 1024-dimensional vectors
- **Framework**: LangChain (structured output, prompt management)

### Infrastructure

- **Containerization**: Docker & Docker Compose
- **ASGI Server**: Uvicorn
- **Caching**: Redis 7
- **PDF Processing**: PyPDF2
- **Text Processing**: spaCy, NLTK patterns

### Development Tools

- **Environment Management**: python-dotenv
- **Logging**: Python logging module
- **Testing**: pytest (implied)
- **Data Analysis**: pandas (data-extractor module)

---

## Core Components

### 1. Case Ingestor (`app/services/case_ingestor.py`)

**Purpose**: Main orchestrator for complete case processing

**Responsibilities**:

- Coordinate PDF parsing
- Trigger AI extraction
- Manage database insertion
- Handle text chunking
- Process words and phrases
- Generate embeddings

**Key Methods**:

- `ingest_pdf_case()`: Main entry point for PDF processing
- `_create_chunk_records()`: Store text chunks with embeddings
- `_process_words()`: Tokenize and index words
- `_extract_phrases()`: Extract and store legal n-grams

**Integration Points**:

- PDF Parser → Text extraction
- AI Extractor → Entity extraction
- Database Inserter → Data persistence
- Word/Phrase Processors → RAG indexing
- Embedding Service → Vector generation

---

### 2. AI Extractor (`app/services/ai_extractor.py`)

**Purpose**: Extract structured legal data from unstructured text using LLMs

**Features**:

- **Dual LLM Support**: Ollama (primary) with OpenAI fallback
- **Structured Output**: Pydantic models enforce schema compliance
- **Washington State Specialization**: Divorce appeals categorization
- **Entity Extraction**: Cases, parties, attorneys, judges, issues, decisions, arguments, citations

**Extraction Pipeline**:

```python
extract_case_data()
    ↓
extract_case_with_ollama()  # Primary
    ↓ (on failure)
extract_case_with_openai()  # Fallback
    ↓
LegalCaseExtraction (Pydantic Model)
```

**Extracted Entities**:

- **Case**: Title, court, dates, outcomes, summary
- **Parties**: Names, legal roles, personal roles
- **Attorneys**: Names, firms, representations
- **Judges**: Names, roles (authoring, concurring, dissenting)
- **Issues**: Category, subcategory, RCW references, decisions
- **Arguments**: Side (appellant/respondent/court), argument text
- **Citations**: Precedent cases with citation formats

**Prompt Engineering** (`prompts.py`):

- System prompts with enum constraints
- Washington State issue hierarchies
- Date extraction patterns (trial/appeal dates)
- Winner determination logic
- Judge extraction patterns

---

### 3. Database Inserter (`app/services/database_inserter.py`)

**Purpose**: Reliable, transactional insertion of all extracted entities

**Architecture**:

- **Sequential ID Assignment**: Database auto-generates all IDs
- **Foreign Key Management**: Automatic relationship tracking
- **Transaction Safety**: Rollback on failure
- **Dimension Resolution**: Lookup/create dimension records

**Insertion Flow**:

```
1. Start Transaction
2. Resolve Dimension IDs (case_type, stage_type, court)
3. Insert Case → Get case_id
4. Insert Parties → Get party_ids
5. Insert Attorneys → Get attorney_ids
6. Insert Judges → Link to case
7. Insert Issues → Get issue_ids
8. Insert Arguments → Link to issues
9. Insert Citations → Link to case
10. Commit Transaction
```

**Key Methods**:

- `insert_complete_case()`: Main transactional insert
- `create_document_record()`: PDF metadata
- `_insert_case()`: Core case data
- `_insert_party()`, `_insert_attorney()`: Entity insertion
- `_parse_date()`: Date normalization

---

### 4. Word Processor (`app/services/word_processor.py`)

**Purpose**: Enable precise word-level indexing for RAG and phrase matching

**Features**:

- **Tokenization**: Legal-aware word splitting
- **Word Dictionary**: Unique word storage with IDs
- **Word Occurrences**: Position tracking (case, chunk, position)
- **Deduplication**: Efficient batch operations

**Schema**:

```sql
word_dictionary (word_id, word)
word_occurrence (case_id, chunk_id, word_id, position)
```

**Use Cases**:

- Exact phrase matching ("child custody")
- Proximity searches (words within N distance)
- Word frequency analysis
- Context window retrieval

---

### 5. Phrase Extractor (`app/services/phrase_extractor.py`)

**Purpose**: Extract and index legal n-grams for terminology discovery

**Features**:

- **N-gram Extraction**: Bigrams, trigrams, 4-grams
- **Legal Filtering**: Focus on legal terminology
- **Frequency Tracking**: Most common legal phrases
- **Contextual Storage**: Chunk-level phrase occurrences

**Legal Phrase Detection**:

- Legal keywords: "court", "judge", "motion", "custody"
- Legal phrases: "due process", "best interests", "child support"
- Citation patterns: "v.", "In re", "ex rel"

**Schema**:

```sql
case_phrases (phrase_id, case_id, phrase, frequency)
```

---

### 6. Context Navigator (`app/services/context_navigator.py`)

**Purpose**: Hierarchical navigation from words to documents

**Navigation Levels**:

1. **Word** → Find all occurrences across cases
2. **Context** → Get surrounding words (window)
3. **Chunk** → Full text chunk containing word
4. **Document** → Complete case with metadata

**Key Features**:

- Word occurrence lookup with case filtering
- Context window generation (N words before/after)
- Chunk retrieval with full text
- Document statistics and full case data

**API Endpoints** (`endpoints/navigation.py`):

- `GET /word/{word}/occurrences`: Find word locations
- `GET /word/{word}/context/{chunk_id}`: Context window
- `GET /chunk/{chunk_id}`: Full chunk text
- `GET /document/{case_id}`: Complete document

---

### 7. Embedding Service (`app/services/embedding_service.py`)

**Purpose**: Generate vector embeddings for semantic search

**Models**:

- **Ollama**: `mxbai-embed-large` (1024-dimensional, primary)
- **OpenAI**: `text-embedding-3-large` (1024-dimensional, fallback)

**Embedding Types**:

- **Case-level**: Title + summary → `cases.full_embedding`
- **Chunk-level**: Individual text chunks → `case_chunks.embedding`

**Functions**:

- `generate_embedding()`: Main entry with fallback logic
- `generate_case_level_embedding()`: Case summaries
- `local_ollama_embed()`: Ollama integration
- `openai_embed()`: OpenAI fallback

---

### 8. PDF Parser (`app/pdf_parser.py`)

**Purpose**: Extract and clean text from PDF documents

**Features**:

- Page-by-page extraction
- Text cleaning and normalization
- Header/footer removal
- PDF artifact fixing
- Punctuation normalization

**Processing Pipeline**:

```
PDF Bytes → PyPDF2 → Raw Text → Cleaning → Page List
```

**Cleaning Operations**:

- Remove page numbers and footers
- Fix hyphenation artifacts
- Normalize whitespace
- Remove legal document headers
- Standardize quotes and dashes

---

### 9. Text Chunker (`app/chunker.py`)

**Purpose**: Segment legal documents into semantic chunks for RAG

**Strategy**:

- **Target Size**: 350 words per chunk
- **Min/Max**: 200-500 words
- **Section Awareness**: Detect legal sections (FACTS, ANALYSIS, HOLDING)
- **Overlap**: Minimal overlap to preserve context

**Legal Sections Detected**:

- HEADER: Court information, case numbers
- PARTIES: Plaintiff, defendant, appellant, respondent
- PROCEDURAL: Procedural history, motions
- FACTS: Statement of facts
- ANALYSIS: Legal analysis, discussion
- HOLDING: Decision, judgment, order

**Output**: `TextChunk` objects with metadata

```python
@dataclass
class TextChunk:
    order: int          # Sequence number
    text: str           # Chunk content
    word_count: int     # Word count
    char_count: int     # Character count
    section: str        # Detected section
```

---

### 10. Dimension Service (`app/services/dimension_service.py`)

**Purpose**: Manage lookup/dimension tables for data normalization

**Managed Dimensions**:

- **case_types**: "divorce", "custody", "support"
- **stage_types**: "trial", "appeal", "supreme"
- **document_types**: "petition", "order", "opinion"
- **courts**: Normalized court information

**Features**:

- **Get-or-Create Pattern**: Automatic creation if missing
- **Caching**: In-memory cache for performance
- **Metadata Resolution**: Convert batch metadata to dimension IDs

**Key Methods**:

- `get_or_create_case_type()`
- `get_or_create_stage_type()`
- `get_or_create_document_type()`
- `get_or_create_court()`
- `resolve_metadata_to_ids()`: Batch metadata → dimension IDs

---

### 11. Sentence Processor (`app/services/sentence_processor.py`)

**Purpose**: Sentence-level indexing for granular text retrieval

**Features**:

- Sentence segmentation
- Sentence storage with embeddings
- Linking to cases and chunks
- Sentence-level search

**Schema**:

```sql
sentences (sentence_id, case_id, chunk_id, text,
           position, word_count, embedding)
```

---

## Data Flow

### Complete PDF Ingestion Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. PDF Upload (batch_processor.py or API endpoint)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. PDF Parser (pdf_parser.py)                                  │
│    • Extract text page-by-page                                 │
│    • Clean and normalize text                                  │
│    • Output: List[str] (pages)                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. AI Extraction (ai_extractor.py)                             │
│    • LLM extraction (Ollama/OpenAI)                            │
│    • Structured output via Pydantic                            │
│    • Output: LegalCaseExtraction                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Database Insertion (database_inserter.py)                   │
│    • Resolve dimensions (case_type, stage, court)              │
│    • Insert case → get case_id                                 │
│    • Insert entities (parties, attorneys, judges, issues)      │
│    • Create document record                                    │
│    • Output: case_id, document_id                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Text Chunking (chunker.py)                                  │
│    • Split text into semantic chunks                           │
│    • Detect legal sections                                     │
│    • Output: List[TextChunk]                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. RAG Indexing (parallel processing)                          │
│                                                                 │
│    ┌─────────────────────┐  ┌─────────────────────┐           │
│    │ Word Processing     │  │ Phrase Extraction   │           │
│    │ • Tokenize text     │  │ • Extract n-grams   │           │
│    │ • Create word dict  │  │ • Filter legal terms│           │
│    │ • Track positions   │  │ • Store frequencies │           │
│    └─────────────────────┘  └─────────────────────┘           │
│                                                                 │
│    ┌─────────────────────┐  ┌─────────────────────┐           │
│    │ Sentence Processing │  │ Embedding Generation│           │
│    │ • Segment sentences │  │ • Case embedding    │           │
│    │ • Store with index  │  │ • Chunk embeddings  │           │
│    └─────────────────────┘  └─────────────────────┘           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Storage Complete                                             │
│    • PostgreSQL tables populated                                │
│    • Vector embeddings indexed                                  │
│    • Ready for search and retrieval                             │
└─────────────────────────────────────────────────────────────────┘
```

### Search Query Flow

```
User Query
    │
    ▼
┌───────────────────────────────────────┐
│ Search Type Selection                 │
├───────────────────────────────────────┤
│ • Semantic (vector similarity)        │
│ • Lexical (exact word match)          │
│ • Phrase (n-gram matching)            │
│ • Hybrid (combine all)                │
└───────────┬───────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ Query Processing                      │
├───────────────────────────────────────┤
│ • Generate query embedding (semantic) │
│ • Tokenize query (lexical)            │
│ • Extract phrases (phrase)            │
└───────────┬───────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ Database Queries                      │
├───────────────────────────────────────┤
│ • Vector similarity: pgvector <=>     │
│ • Word lookup: word_occurrence JOIN   │
│ • Phrase match: case_phrases          │
└───────────┬───────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ Result Ranking & Fusion               │
├───────────────────────────────────────┤
│ • Reciprocal Rank Fusion (RRF)        │
│ • Score normalization                 │
│ • Deduplication                       │
└───────────┬───────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│ Context Enrichment                    │
├───────────────────────────────────────┤
│ • Retrieve chunk metadata             │
│ • Get case information                │
│ • Include citations/parties           │
└───────────┬───────────────────────────┘
            │
            ▼
      Return Results
```

---

## Database Schema

### ER Diagram (Simplified)

```
┌────────────────┐          ┌────────────────┐
│  case_types    │          │  stage_types   │
│  (dimension)   │          │  (dimension)   │
└────────┬───────┘          └────────┬───────┘
         │                           │
         └──────────┬────────────────┘
                    │
                    ▼
              ┌──────────┐
              │  cases   │ (Central Entity)
              └─────┬────┘
                    │
         ┌──────────┼──────────┬─────────────┬─────────────┐
         │          │          │             │             │
         ▼          ▼          ▼             ▼             ▼
    ┌────────┐ ┌─────────┐ ┌──────┐    ┌─────────┐  ┌──────────┐
    │parties │ │attorneys│ │judges│    │documents│  │citations │
    └────────┘ └─────────┘ └──────┘    └────┬────┘  └──────────┘
                                             │
                    ┌────────────────────────┘
                    │
         ┌──────────┼──────────┬──────────────┐
         ▼          ▼          ▼              ▼
  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
  │case_chunks │ │issues_   │ │arguments  │ │sentences │
  │            │ │decisions │ │           │ │          │
  └──────┬─────┘ └──────────┘ └───────────┘ └──────────┘
         │
         ├────────────┬─────────────┬──────────────┐
         ▼            ▼             ▼              ▼
  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
  │word_        │ │word_     │ │case_     │ │anchors   │
  │dictionary   │ │occurrence│ │phrases   │ │          │
  └─────────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Table Categories

#### 1. Dimension Tables (Lookup/Reference)

```sql
case_types (case_type_id, case_type, description, jurisdiction)
stage_types (stage_type_id, stage_type, level)
document_types (document_type_id, document_type, has_decision)
courts_dim (court_id, court, level, jurisdiction, district, county)
statutes_dim (statute_id, jurisdiction, code, title, section, display_text)
```

#### 2. Core Entity Tables

```sql
cases (case_id PK, title, court_level, dates, outcomes, embeddings, FKs)
parties (party_id PK, case_id FK, name, legal_role, personal_role)
attorneys (attorney_id PK, case_id FK, name, firm, representing)
judges (judge_id PK, case_id FK, judge_name, role)
issues_decisions (issue_id PK, case_id FK, category, subcategory, outcomes)
arguments (argument_id PK, case_id FK, issue_id FK, side, argument_text)
citations (citation_id PK, citing_case_id FK, cited_case_id FK)
```

#### 3. Document Management Tables

```sql
documents (document_id PK, case_id FK, stage_type_id FK,
           document_type_id FK, metadata, processing_status)
```

#### 4. RAG/Search Tables

```sql
-- Chunking
case_chunks (chunk_id PK, case_id FK, chunk_order, text,
             section, embedding VECTOR(1024))

-- Word Indexing
word_dictionary (word_id PK, word UNIQUE)
word_occurrence (case_id FK, chunk_id FK, word_id FK, position)

-- Phrase Indexing
case_phrases (phrase_id PK, case_id FK, phrase, frequency)

-- Sentence Indexing
sentences (sentence_id PK, case_id FK, chunk_id FK, text,
           position, embedding VECTOR(1024))

-- Anchors (Named Locations)
anchors (anchor_id PK, case_id FK, chunk_id FK, anchor_type,
         label, position)

-- Citations
statute_citations (citation_id PK, case_id FK, statute_id FK,
                   chunk_id FK, context)
```

### Key Indexes

```sql
-- Performance indexes
CREATE INDEX idx_cases_case_type_id ON cases(case_type_id);
CREATE INDEX idx_cases_court_id ON cases(court_id);
CREATE INDEX idx_documents_case_id ON documents(case_id);
CREATE INDEX idx_case_chunks_case_id ON case_chunks(case_id);
CREATE INDEX idx_word_occurrence_word_id ON word_occurrence(word_id);
CREATE INDEX idx_word_occurrence_case_id ON word_occurrence(case_id);

-- Vector similarity indexes (automatically created by pgvector)
CREATE INDEX idx_cases_embedding ON cases USING ivfflat (full_embedding vector_cosine_ops);
CREATE INDEX idx_chunks_embedding ON case_chunks USING ivfflat (embedding vector_cosine_ops);

-- Full-text search indexes
CREATE INDEX idx_cases_title_gin ON cases USING gin(to_tsvector('english', title));
CREATE INDEX idx_cases_summary_gin ON cases USING gin(to_tsvector('english', summary));
```

### Washington State Issue Categorization

The `issues_decisions` table uses a hierarchical categorization specific to Washington State family law:

```python
CATEGORIES = [
    "Spousal Support / Maintenance",
    "Child Support",
    "Parenting Plan / Custody / Visitation",
    "Property Division / Debt Allocation",
    "Attorney Fees & Costs",
    "Procedural & Evidentiary Issues",
    "Jurisdiction & Venue",
    "Enforcement & Contempt Orders",
    "Modification Orders",
    "Miscellaneous / Unclassified"
]

SUBCATEGORIES_EXAMPLE = {
    "Spousal Support / Maintenance": [
        "Duration (temp vs. permanent)",
        "Amount calculation errors",
        "Imputed income disputes",
        "Failure to consider statutory factors"
    ]
}

RCW_REFERENCES = [
    "RCW 26.09.090",  # Spousal maintenance
    "RCW 26.19.071",  # Child support
    # ... etc
]
```

---

## API Architecture

### FastAPI Application Structure

```
app/
├── main.py                    # FastAPI app initialization
├── core/
│   └── config.py             # Settings, environment config
├── api/
│   └── v1/
│       ├── api.py            # Route aggregation
│       └── endpoints/
│           ├── health.py     # Health checks
│           ├── cases.py      # Case CRUD operations
│           ├── batch.py      # Batch processing API
│           ├── navigation.py # Word-to-document navigation
│           ├── ocr.py        # OCR processing (if needed)
│           └── excel_upload.py # Excel import (disabled)
```

### API Endpoint Groups

#### 1. Health & Status (`/api/v1/health/`)

```
GET /health               - System health check
GET /health/database      - Database connectivity
GET /health/ollama        - Ollama availability
GET /health/redis         - Redis connectivity
```

#### 2. Case Management (`/api/v1/cases/`)

```
GET    /cases                    - List cases (paginated)
GET    /cases/{case_id}          - Get case details
POST   /cases                    - Create case (manual)
PUT    /cases/{case_id}          - Update case
DELETE /cases/{case_id}          - Delete case
GET    /cases/search             - Search cases
GET    /cases/{case_id}/parties  - Get case parties
GET    /cases/{case_id}/issues   - Get case issues
```

#### 3. Batch Processing (`/api/v1/batch/`)

```
POST   /batch/upload-pdfs        - Upload PDFs for processing
GET    /batch/status/{job_id}    - Get processing status
GET    /batch/results/{job_id}   - Get processing results
POST   /batch/process-directory  - Process directory of PDFs
```

#### 4. Navigation API (`/api/v1/navigation/`)

```
GET /word/{word}/occurrences           - Find word occurrences
GET /word/{word}/context/{chunk_id}    - Get context window
GET /chunk/{chunk_id}                  - Get full chunk
GET /document/{case_id}                - Get full document
GET /phrases/top                       - Most common phrases
GET /phrases/{phrase}/occurrences      - Find phrase
```

#### 5. Search API (Implied/Future)

```
POST /search/semantic              - Vector similarity search
POST /search/lexical               - Keyword search
POST /search/phrase                - Phrase search
POST /search/hybrid                - Combined search
```

### Request/Response Models (Pydantic)

#### Navigation Models

```python
class WordOccurrence(BaseModel):
    case_id: int
    chunk_id: int
    position: int
    word: str
    section: Optional[str]
    chunk_order: int
    case_title: str
    court: Optional[str]
    chunk_preview: str

class ContextWindow(BaseModel):
    target_word: str
    target_position: Optional[int]
    chunk_id: int
    context_sentence: str
    window_size: int

class ChunkData(BaseModel):
    chunk_id: int
    case_id: int
    text: str
    case_title: str
    statistics: Dict
```

#### Batch Processing Models

```python
class BatchProcessingStatus(BaseModel):
    job_id: str
    status: str  # "running", "completed", "failed"
    processed_files: int
    total_files: int
    current_file: Optional[str]
    message: str

class ProcessingResult(BaseModel):
    success: bool
    case_id: Optional[str]
    filename: str
    message: str
    processing_time: Optional[float]
```

### CORS Configuration

```python
BACKEND_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080"
]
```

### API Versioning

- Current: `/api/v1/`
- Future versions can be added as `/api/v2/` without breaking existing clients

---

## AI/ML Pipeline

### LLM Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Extraction Request                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               Prompt Engineering Layer                       │
│  • System prompt (rules, enums, patterns)                   │
│  • Human template (case info + case text)                   │
│  • Washington State issue hierarchy                         │
│  • Date/entity extraction patterns                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   LLM Selection Logic                        │
│  1. Try Ollama (if USE_OLLAMA=true)                         │
│  2. Fallback to OpenAI (if API key available)               │
│  3. Retry Ollama if OpenAI fails                            │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌──────────────────┐         ┌──────────────────────┐
│  Ollama Client   │         │   OpenAI Client      │
│  (qwen:32b)      │         │   (gpt-4o-mini)      │
│  • Native SDK    │         │   • LangChain        │
│  • JSON mode     │         │   • Structured out   │
│  • Local         │         │   • Cloud API        │
└────────┬─────────┘         └──────────┬───────────┘
         │                              │
         └──────────────┬───────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Pydantic Validation Layer                       │
│  • LegalCaseExtraction.model_validate_json()                │
│  • Enum validation (CourtLevel, LegalRole, etc.)            │
│  • Date parsing and normalization                           │
│  • Field validation (required, optional)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Structured Output (Validated)                   │
│  • LegalCaseExtraction (main model)                         │
│  • All entities with validated fields                       │
│  • Ready for database insertion                             │
└─────────────────────────────────────────────────────────────┘
```

### Pydantic Models Hierarchy

```python
LegalCaseExtraction
├── case: CaseInformation
│   ├── title: str
│   ├── court_level: CourtLevel (enum)
│   ├── district: District (enum)
│   ├── dates: DateField (multiple)
│   ├── outcomes: AppealOutcome (enum)
│   └── ... (25+ fields)
├── parties: List[Party]
│   ├── name: str
│   ├── legal_role: LegalRole (enum)
│   └── personal_role: PersonalRole (enum)
├── attorneys: List[Attorney]
│   ├── name: str
│   ├── firm_name: Optional[str]
│   └── representing: LegalRole (enum)
├── appeals_judges: List[Judge]
│   ├── judge_name: str
│   └── role: JudgeRole (enum)
├── issues_decisions: List[IssueDecision]
│   ├── category: str (from hierarchy)
│   ├── subcategory: str
│   ├── rcw_reference: Optional[str]
│   ├── decision_summary: str
│   └── winner: DecisionWinner (enum)
├── arguments: List[Argument]
│   ├── side: ArgumentSide (enum)
│   └── argument_text: str
└── precedents: List[Citation]
    ├── citation: str
    └── relevance: str
```

### Embedding Pipeline

```
Text Input
    │
    ▼
┌─────────────────────────────┐
│ Embedding Generation Logic  │
│ • prefer_ollama=True        │
│ • ollama_only=False         │
└──────────┬──────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐   ┌─────────┐
│ Ollama  │   │ OpenAI  │
│ mxbai   │   │ text-   │
│ -embed  │   │ embed-  │
│ -large  │   │ 3-large │
└────┬────┘   └────┬────┘
     │             │
     └──────┬──────┘
            ▼
   Vector(1024 dimensions)
            │
            ▼
   ┌────────────────┐
   │ PostgreSQL     │
   │ (pgvector)     │
   └────────────────┘
```

### Prompt Engineering Highlights

**System Prompt Features**:

- Enum value constraints (exact matches required)
- Washington State issue hierarchies (10 categories, 50+ subcategories)
- Date extraction patterns (trial dates, appeal dates, filing dates)
- Entity extraction rules (judges, attorneys, parties)
- Winner determination logic (outcome-based)
- RCW statute references

**Key Extraction Patterns**:

```
DATES:
- "FILED: [date]" → appeal_published_date
- "trial began on [date]" → trial_start_date
- "judgment entered on [date]" → trial_published_date

JUDGES:
- "Authored by [Name]" → judge with role "Authored by"
- "Concurring: [Name]" → judge with role "Concurring"
- "[Name], J." → extract judge name

OUTCOMES:
- "affirmed" → respondent wins
- "reversed" → appellant wins
- "remanded" → appellant wins (partial)
```

---

## Deployment Architecture

### Docker Compose Stack

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5433:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-postgres.sh:/docker-entrypoint-initdb.d/
    environment:
      POSTGRES_PASSWORD: postgres
    command: >
      postgres -c shared_preload_libraries=vector
               -c max_connections=200

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      - DATABASE_URL=postgresql://legal_user:legal_pass@postgres:5432/cases_llama3.3
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OLLAMA_EMBED_MODEL=${OLLAMA_EMBED_MODEL}
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
```

### Environment Configuration

**Auto-Detection** (Smart Environment Detection):

```python
# config.py automatically detects Docker vs local
@property
def database_host(self) -> str:
    """Auto-detect if running inside Docker or locally"""
    try:
        socket.gethostbyname("legal_ai_postgres")
        return "legal_ai_postgres"  # Inside Docker
    except socket.gaierror:
        return "localhost"  # Outside Docker
```

**Environment Variables**:

```bash
# Database
DATABASE_URL=postgresql://legal_user:legal_pass@localhost:5433/cases_llama3.3
PGHOST=localhost
PGPORT=5433
PGDATABASE=cases_llama3.3
PGUSER=legal_user
PGPASSWORD=legal_pass

# AI/LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OLLAMA_MODEL=qwen:32b
OLLAMA_EMBED_MODEL=mxbai-embed-large
OLLAMA_BASE_URL=http://localhost:11434
USE_OLLAMA=true

# Server
SERVER_HOST=localhost
SERVER_PORT=8000
DEBUG=true
```

### Container Health Checks

```dockerfile
# API Health Check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# PostgreSQL Health Check
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 10s
  timeout: 5s
  retries: 5

# Redis Health Check
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 5s
  retries: 3
```

### Startup Sequence

```bash
1. PostgreSQL Starts
   ↓
2. Run init-postgres.sh
   ↓
3. Create database and extensions
   ↓
4. Run init-db.sql (schema creation)
   ↓
5. Redis Starts
   ↓
6. API Container Starts
   ↓
7. docker-entrypoint.sh
   ↓
8. Wait for database ready
   ↓
9. Start Uvicorn server
   ↓
10. API Ready (port 8000)
```

### Database Initialization

```bash
# scripts/init-postgres.sh
#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE "cases_llama3.3";
    CREATE USER legal_user WITH PASSWORD 'legal_pass';
    GRANT ALL PRIVILEGES ON DATABASE "cases_llama3.3" TO legal_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d "cases_llama3.3" < /app/init-db.sql
```

---

## Directory Structure

```
Postgres_Ingestion_LegalAI/
│
├── app/                              # Main FastAPI application
│   ├── __init__.py
│   ├── main.py                       # FastAPI app entry point
│   ├── database.py                   # SQLAlchemy engine setup
│   ├── pdf_parser.py                 # PDF text extraction
│   ├── chunker.py                    # Text chunking logic
│   │
│   ├── core/                         # Core configuration
│   │   ├── __init__.py
│   │   └── config.py                 # Settings (auto-detection)
│   │
│   ├── api/                          # API layer
│   │   ├── __init__.py
│   │   └── v1/                       # API version 1
│   │       ├── __init__.py
│   │       ├── api.py                # Route aggregation
│   │       └── endpoints/            # API endpoints
│   │           ├── __init__.py
│   │           ├── batch.py          # Batch processing API
│   │           ├── cases.py          # Case CRUD
│   │           ├── health.py         # Health checks
│   │           ├── navigation.py     # Word navigation
│   │           ├── ocr.py            # OCR processing
│   │           └── excel_upload.py   # Excel import (disabled)
│   │
│   ├── models/                       # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── cases.py                  # Case model
│   │   ├── parties.py                # Party model
│   │   ├── attorneys.py              # Attorney model
│   │   ├── judges.py                 # Judge model
│   │   ├── issues.py                 # Issue model
│   │   ├── citations.py              # Citation model
│   │   ├── chunks.py                 # Chunk model
│   │   ├── words.py                  # Word models
│   │   ├── phrases.py                # Phrase model
│   │   ├── sentences.py              # Sentence model
│   │   ├── anchors.py                # Anchor model
│   │   ├── case_types.py             # Case type dimension
│   │   ├── stage_types.py            # Stage type dimension
│   │   ├── document_types.py         # Document type dimension
│   │   ├── courts.py                 # Court dimension
│   │   ├── documents.py              # Document model
│   │   ├── statutes.py               # Statute dimension
│   │   └── statute_citations.py      # Statute citation model
│   │
│   └── services/                     # Business logic layer
│       ├── __init__.py
│       ├── ai_extractor.py           # LLM extraction service
│       ├── case_ingestor.py          # Main orchestrator
│       ├── database_inserter.py      # Database insertion
│       ├── word_processor.py         # Word indexing
│       ├── phrase_extractor.py       # Phrase extraction
│       ├── sentence_processor.py     # Sentence indexing
│       ├── context_navigator.py      # Word-to-document navigation
│       ├── embedding_service.py      # Vector embeddings
│       ├── dimension_service.py      # Dimension table management
│       ├── models.py                 # Pydantic models for extraction
│       └── prompts.py                # LLM prompts
│
├── data-extractor/                   # Standalone data extraction tool
│   ├── data_extractor.py             # Main extraction script
│   ├── example_usage.py              # Usage examples
│   ├── requirements.txt              # Dependencies
│   ├── config.env.example            # Config template
│   ├── sample_data.csv               # Sample data
│   ├── README.md                     # Documentation
│   ├── README_SIMPLE.md              # Simplified guide
│   └── RUN_*.bat/ps1/sh              # Run scripts
│
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # This file
│   ├── README.md                     # Main documentation
│   ├── DATABASE_STRUCTURE_FOR_AI.md  # Database guide
│   ├── TEXT_RETRIEVAL_DATABASE_SCHEMA.md # RAG schema
│   ├── BATCH_PROCESSING_GUIDE.md     # Batch processing guide
│   ├── DEPLOYMENT_CHECKLIST.md       # Deployment steps
│   ├── MIGRATION_GUIDE.md            # Migration instructions
│   ├── SUPERVISOR_ROUTING_GUIDE.md   # Agent routing (if applicable)
│   └── README_CLEAN_SYSTEM.md        # Clean install guide
│
├── scripts/                          # Utility scripts
│   ├── docker-entrypoint.sh          # Container startup
│   ├── init-postgres.sh              # Database initialization
│   ├── startup.sh                    # Startup script
│   ├── reset_database.py             # Database reset (Python)
│   ├── reset_database.sh             # Database reset (Bash)
│   ├── verify_database.py            # Database verification
│   └── README_DATABASE_RESET.md      # Reset instructions
│
├── batch_processor.py                # CLI batch processor
├── database_initializer.py           # Database setup utility
├── docker-compose.yml                # Docker Compose config
├── Dockerfile                        # API container image
├── init-db.sql                       # PostgreSQL schema
├── requirements.txt                  # Python dependencies
├── .env                              # Environment variables (gitignored)
├── README.md                         # Project README
├── PRODUCTION_RESTART_GUIDE.md       # Production operations
├── restart.sh                        # Restart script
├── law_helper_schema.dbml            # DBML schema definition
└── commands.txt                      # Common commands reference
```

### Key Files Description

**Root Level**:

- `batch_processor.py`: CLI tool for batch PDF processing
- `database_initializer.py`: Database initialization and verification
- `docker-compose.yml`: Multi-container orchestration
- `Dockerfile`: API container definition
- `init-db.sql`: Complete PostgreSQL schema (465 lines)
- `requirements.txt`: Python dependencies (FastAPI, SQLAlchemy, LangChain, etc.)

**App Layer**:

- `app/main.py`: FastAPI application initialization, CORS, routes
- `app/database.py`: SQLAlchemy engine with auto-detection
- `app/pdf_parser.py`: PyPDF2-based text extraction with cleaning
- `app/chunker.py`: Legal-aware text chunking

**Service Layer** (Core Business Logic):

- `ai_extractor.py`: Ollama/OpenAI integration with structured output
- `case_ingestor.py`: Main orchestrator (550+ lines)
- `database_inserter.py`: Transactional entity insertion (450+ lines)
- `word_processor.py`: Word tokenization and position tracking (366 lines)
- `phrase_extractor.py`: N-gram extraction and legal filtering (341 lines)
- `context_navigator.py`: Hierarchical navigation (405 lines)
- `embedding_service.py`: Vector generation with fallbacks (212 lines)
- `dimension_service.py`: Lookup table management (231 lines)

**Pydantic Models** (`services/models.py`):

- 629 lines of structured extraction models
- 15+ enums for legal terminology
- Comprehensive field validation

**Prompts** (`services/prompts.py`):

- 241 lines of carefully crafted prompts
- Washington State issue hierarchies
- Date/entity extraction patterns

---

## Key Design Patterns

### 1. Orchestrator Pattern

`LegalCaseIngestor` acts as the main orchestrator, coordinating multiple services:

```python
class LegalCaseIngestor:
    def ingest_pdf_case(self):
        # 1. Parse PDF
        # 2. AI Extraction
        # 3. Database Insertion
        # 4. Text Chunking
        # 5. Word Processing
        # 6. Phrase Extraction
        # 7. Embedding Generation
```

### 2. Fallback Pattern

Multiple layers of fallbacks for reliability:

```python
# AI Extraction: Ollama → OpenAI → Retry Ollama
# Embedding: Ollama → OpenAI
# Environment: Docker → Localhost (auto-detection)
```

### 3. Get-or-Create Pattern

Dimension service uses get-or-create for lookups:

```python
def get_or_create_case_type(self, case_type: str) -> int:
    # Try to find existing
    # Create if not found
    # Cache result
```

### 4. Transaction Pattern

Database inserter uses transactions for atomicity:

```python
with conn.begin() as trans:
    try:
        # Insert all entities
        trans.commit()
    except:
        trans.rollback()
```

### 5. Service Layer Pattern

Business logic separated from API and data layers:

```
API → Service → Database
```

### 6. Pydantic Validation Pattern

All external data validated through Pydantic:

```python
result = LegalCaseExtraction.model_validate_json(llm_output)
```

### 7. Hierarchical Navigation Pattern

Progressive drill-down from words to documents:

```
Word → Occurrences → Context → Chunk → Document
```

---

## Performance Considerations

### Database Optimizations

1. **Indexes**: Vector (IVFFLAT), B-tree (foreign keys), GIN (full-text)
2. **Connection Pooling**: SQLAlchemy engine with connection pooling
3. **Bulk Operations**: Batch word/phrase insertions
4. **Caching**: Redis for frequently accessed data
5. **Prepared Statements**: Parameterized queries

### AI/ML Optimizations

1. **Local LLM**: Ollama for cost-free extraction
2. **Streaming**: Process PDFs page-by-page
3. **Parallel Processing**: Independent services can run in parallel
4. **Embedding Caching**: Case-level embeddings cached
5. **Model Selection**: Appropriate model sizes (qwen:32b, mxbai-embed-large)

### API Optimizations

1. **Async FastAPI**: Non-blocking I/O
2. **Background Tasks**: Long-running processing in background
3. **Pagination**: Large result sets paginated
4. **Response Models**: Minimal data transfer (previews, not full text)

---

## Security Considerations

### Database Security

- Separate database user (`legal_user`) with limited privileges
- Parameterized queries (SQL injection prevention)
- No passwords in code (environment variables)
- Connection string encryption in production

### API Security

- CORS configured for allowed origins
- Input validation via Pydantic
- File upload size limits
- API versioning for backward compatibility

### Secrets Management

- `.env` file for local development (gitignored)
- Environment variables for Docker
- No secrets in codebase or version control

---

## Monitoring & Logging

### Logging Configuration

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_processing.log')
    ]
)
```

### Health Checks

- `/api/v1/health/` - Overall system health
- Database connectivity checks
- Ollama availability checks
- Redis connectivity checks
- Container health checks (Docker)

### Metrics to Monitor

- PDF processing time
- AI extraction success rate
- Database query performance
- API response times
- Vector similarity search latency
- Error rates by endpoint

---

## Future Enhancements

### Planned Features

1. **Advanced Search**:

   - Hybrid search combining semantic + lexical + phrase
   - Reciprocal Rank Fusion (RRF) for result merging
   - Faceted search (by court, date range, issue category)

2. **Enhanced RAG**:

   - Chunk-level embeddings (currently case-level only)
   - Sentence embeddings for fine-grained retrieval
   - Context-aware chunk retrieval

3. **Additional Extractions**:

   - Statute citations with section references
   - Legal entity relationships (party-attorney links)
   - Timeline generation from dates

4. **Performance**:

   - Query result caching
   - Incremental indexing
   - Parallel PDF processing

5. **UI/UX**:
   - Web-based search interface
   - Visual timeline of case events
   - Citation graph visualization

### Potential Optimizations

1. **Database**:

   - Partition large tables by date
   - Materialized views for common queries
   - Read replicas for scaling

2. **AI/ML**:

   - Fine-tune Ollama models on legal text
   - Custom legal embeddings
   - Streaming LLM responses

3. **Architecture**:
   - Microservices for independent scaling
   - Message queue for async processing (RabbitMQ/Kafka)
   - Distributed embeddings (Qdrant/Weaviate)

---

## Appendix

### Common Commands

```bash
# Start system
docker-compose up -d

# View logs
docker-compose logs -f api

# Batch process PDFs
python batch_processor.py ./case-pdfs/ --limit 10 --verbose

# Access API docs
open http://localhost:8000/docs

# Database connection
psql -h localhost -p 5433 -U legal_user -d cases_llama3.3

# Reset database
python scripts/reset_database.py

# Verify database
python scripts/verify_database.py
```

### Environment Setup

```bash
# Python virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Setup .env
cp .env.example .env
# Edit .env with your settings
```

### Ollama Setup

```bash
# Install Ollama (Linux/Mac)
curl https://ollama.ai/install.sh | sh

# Pull models
ollama pull qwen:32b              # Extraction model
ollama pull mxbai-embed-large     # Embedding model

# Start Ollama server
ollama serve
```

### Docker Commands

```bash
# Build and start
docker-compose up --build -d

# Stop
docker-compose down

# Remove volumes (clean slate)
docker-compose down -v

# View container status
docker-compose ps

# Execute command in container
docker-compose exec api python batch_processor.py --help
```

---

## References

### External Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Ollama Documentation](https://ollama.ai/docs)
- [LangChain Documentation](https://python.langchain.com/)

### Internal Documentation

- `docs/README.md` - Main documentation
- `docs/DATABASE_STRUCTURE_FOR_AI.md` - Database schema details
- `docs/BATCH_PROCESSING_GUIDE.md` - Batch processing guide
- `docs/DEPLOYMENT_CHECKLIST.md` - Deployment steps
- `README.md` - Quick start guide

---

## Contact & Support

For questions about this architecture or the system:

1. Review the documentation in `docs/`
2. Check API documentation at `/docs` when system is running
3. Review code comments in source files
4. Check logs in `batch_processing.log` and Docker logs

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-20  
**System Version**: 1.0.0
