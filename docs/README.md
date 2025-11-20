# Law Helper - Legal Case Ingestion System

A comprehensive FastAPI service for ingesting legal case documents into a PostgreSQL database with full-text search capabilities.

## 🎯 **What This System Does**

This system accepts PDF legal case files, processes them through a complete ingestion pipeline, and stores structured data in PostgreSQL for efficient search and retrieval.

### **Ingestion Pipeline**
1. **PDF Upload** → Accept PDF files with metadata via REST API
2. **Text Extraction** → Parse PDF pages and clean text
3. **Text Chunking** → Split into semantic chunks (300-500 words)
4. **Word Indexing** → Tokenize and build position-based word index
5. **Database Storage** → Store everything transactionally in PostgreSQL

## 🏗️ **Architecture**

### **Database Schema**
```sql
cases (case metadata)
 └── case_chunks (paragraph-sized text)
      └── word_occurrence (word position data)
           └── word_dictionary (unique word list)
```

### **Key Features**
- **Exact phrase search** via word position indexing
- **Transactional processing** (all-or-nothing ingestion)
- **Legal document optimization** (handles court formatting, citations)
- **Batch word processing** for performance
- **Comprehensive logging** and error handling

## 🚀 **Quick Start**

### 1. Start the Database
```bash
docker-compose up -d
```

### 2. Install Dependencies
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the API Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Upload a Case
```bash
./example_upload.sh /path/to/your/case.pdf
```

## 📋 **API Endpoints**

### **Case Upload**
```http
POST /api/v1/cases/upload
Content-Type: multipart/form-data

{
  "pdf_file": <file>,
  "metadata": {
    "title": "In re Marriage of Townley",
    "court": "Court of Appeals of Washington", 
    "docket_number": "39265-1-III",
    "filing_date": "2024-03-07"
  }
}
```

**Response:**
```json
{
  "case_id": "uuid-generated",
  "status": "success",
  "stats": {
    "pages": 15,
    "chunks": 45,
    "total_words": 12543,
    "unique_words": 2387,
    "word_occurrences": 12543
  }
}
```

### **Phrase Search**
```http
GET /api/v1/cases/search/phrase?query=business%20expenses&limit=10
```

**Response:**
```json
{
  "query": "business expenses",
  "results": [
    {
      "case_id": "uuid",
      "case_title": "In re Marriage of Townley",
      "chunk_id": "uuid",
      "chunk_order": 23,
      "chunk_text": "The court found that business expenses...",
      "position": 45
    }
  ],
  "total_found": 3
}
```

### **Verify Ingestion**
```http
GET /api/v1/cases/verify/{case_id}
```

### **Database Stats**
```http
GET /api/v1/cases/stats
```

## 📁 **Project Structure**

```
app/
├── api/v1/endpoints/
│   ├── cases.py              # Case upload & search endpoints
│   ├── health.py             # Health check
│   └── ocr.py                # OCR processing
├── database.py               # SQLAlchemy models & DB setup
├── pdf_parser.py             # PDF text extraction & cleaning
├── chunker.py                # Text chunking with legal awareness
├── word_indexer.py           # Word tokenization & indexing
├── ingest.py                 # Complete ingestion orchestration
└── main.py                   # FastAPI application

docker-compose.yml            # PostgreSQL + Redis setup
init-db.sql                   # Database initialization
example_upload.sh             # Example upload script
```

## 🔧 **Database Design Deep Dive**

### **Why This Schema?**

Legal documents are large and hierarchical. This design enables:
- **Hybrid search**: Semantic (via chunks) + keyword (via word index)
- **Exact phrase matching**: Word position tracking
- **Efficient storage**: Word normalization prevents duplication
- **Scalable performance**: Proper indexing for large datasets

### **Table Details**

#### `cases`
```sql
case_id          UUID PRIMARY KEY
title            CITEXT NOT NULL
court            CITEXT  
docket_number    CITEXT
filing_date      DATE
created_at       TIMESTAMP
```

#### `case_chunks`
```sql
chunk_id         UUID PRIMARY KEY
case_id          UUID → cases(case_id)
chunk_order      INTEGER NOT NULL
chunk_text       TEXT NOT NULL
```

#### `word_dictionary`
```sql
word_id          SERIAL PRIMARY KEY  
word_text        CITEXT UNIQUE NOT NULL
```

#### `word_occurrence`
```sql
occurrence_id    SERIAL PRIMARY KEY
case_id          UUID → cases(case_id)
chunk_id         UUID → case_chunks(chunk_id)  
word_id          INTEGER → word_dictionary(word_id)
position_index   INTEGER NOT NULL
```

### **Example Queries**

**Find phrase "business expenses":**
```sql
SELECT c.title, cc.chunk_text, w1.position_index
FROM cases c
JOIN case_chunks cc ON cc.case_id = c.case_id
JOIN word_occurrence w1 ON w1.chunk_id = cc.chunk_id
JOIN word_occurrence w2 ON w2.chunk_id = cc.chunk_id
JOIN word_dictionary wd1 ON wd1.word_id = w1.word_id
JOIN word_dictionary wd2 ON wd2.word_id = w2.word_id
WHERE wd1.word_text = 'business'
  AND wd2.word_text = 'expenses'
  AND w2.position_index = w1.position_index + 1;
```

## 🔍 **Text Processing Details**

### **PDF Parser (`pdf_parser.py`)**
- Extracts text from PDF pages using PyPDF2
- Cleans artifacts (broken words, spacing issues)
- Removes headers/footers common in legal docs
- Normalizes punctuation and quotes

### **Text Chunker (`chunker.py`)**
- Splits text into 300-500 word semantic chunks
- Recognizes legal document sections (FACTS, ANALYSIS, etc.)
- Maintains chunk order for document reconstruction
- Handles section boundaries intelligently

### **Word Indexer (`word_indexer.py`)**
- Tokenizes with legal-aware patterns
- Preserves legal citations and abbreviations
- Builds position-based word occurrence index
- Supports exact phrase and proximity search

## 🎛️ **Configuration**

### **Environment Variables**
```bash
DATABASE_URL=postgresql://legal_user:legal_pass@localhost:5432/legal_ai
SERVER_HOST=localhost
SERVER_PORT=8000
DEBUG=true
```

### **Chunking Parameters**
```python
target_chunk_size=350    # Target words per chunk
min_chunk_size=200       # Minimum chunk size
max_chunk_size=500       # Maximum chunk size
```

## 🧪 **Testing**

### **Upload Test Case**
```bash
# Create a test PDF or use existing legal document
./example_upload.sh /path/to/test-case.pdf

# Verify ingestion
curl "http://localhost:8000/api/v1/cases/verify/YOUR_CASE_ID"

# Test phrase search  
curl "http://localhost:8000/api/v1/cases/search/phrase?query=contract%20breach"
```

### **Check Database**
```sql
-- Connect to database
psql -h localhost -U legal_user -d legal_ai

-- Check ingested data
SELECT COUNT(*) FROM cases;
SELECT COUNT(*) FROM case_chunks;
SELECT COUNT(*) FROM word_dictionary;
SELECT COUNT(*) FROM word_occurrence;

-- View sample case
SELECT title, created_at FROM cases LIMIT 5;
```

## 📊 **Performance Considerations**

- **Batch inserts** for word occurrences (handles large volumes)
- **Proper indexing** on chunk_id, word_id, position_index
- **CITEXT** for case-insensitive matching
- **Transactional processing** ensures data consistency
- **Connection pooling** for concurrent requests

## 🔮 **Future Extensions**

This foundation supports easy addition of:
- **Semantic search** (embeddings on chunks)
- **RAG pipelines** (retrieval from chunks)
- **Citation networks** (case-to-case relationships)
- **Entity extraction** (parties, judges, statutes)
- **Summarization** (per chunk or case)
- **Analytics** (phrase frequency, court patterns)

## 🐛 **Troubleshooting**

### **Common Issues**

1. **Database connection failed**
   ```bash
   docker-compose up -d postgres
   # Wait for startup, then check logs
   docker-compose logs postgres
   ```

2. **PDF parsing errors**
   - Ensure PDF is text-based (not scanned images)
   - Check PDF file size (max 50MB)
   - Verify file is not corrupted

3. **Empty search results**
   - Check word exists: `SELECT * FROM word_dictionary WHERE word_text = 'yourword';`
   - Verify case ingestion: Use `/api/v1/cases/verify/{case_id}`

### **Logs**
```bash
# API logs
uvicorn app.main:app --reload --log-level debug

# Database logs  
docker-compose logs postgres
```

## 📄 **License**

MIT License - See LICENSE file for details.

---

**Ready to ingest your legal documents!** 🏛️⚖️