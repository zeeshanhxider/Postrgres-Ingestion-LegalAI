# 🏛️ Law Helper - Legal Case Processing & RAG System

A comprehensive legal document processing system with AI extraction, RAG capabilities, and intelligent navigation.

## 🚀 Quick Start

### 1. Start the System
```bash
# Start database and services
docker-compose up -d

# Activate virtual environment
source venv/bin/activate

# Run the FastAPI server
python app/main.py
```

### 2. Process PDF Cases
```bash
# Process all PDFs in a directory
python batch_processor.py ./case-pdfs/

# Process with limit
python batch_processor.py ./case-pdfs/ --limit 10

# Verbose logging
python batch_processor.py ./case-pdfs/ --verbose
```

### 3. Access the API
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

## 📊 System Architecture

### Core Components

#### 🤖 AI Extraction (`app/services/`)
- **`ai_extractor.py`** - Ollama & OpenAI integration with structured output
- **`models.py`** - Pydantic models with Washington State divorce categorization
- **`prompts.py`** - Optimized prompts for legal document analysis

#### 🔄 Data Processing (`app/services/`)
- **`case_ingestor.py`** - Main orchestrator for complete case processing
- **`database_inserter.py`** - Raw SQL insertions for all entities
- **`word_processor.py`** - Word tokenization and position tracking
- **`phrase_extractor.py`** - Legal n-gram discovery and indexing
- **`context_navigator.py`** - Word-to-document navigation

#### 🌐 FastAPI Application (`app/`)
- **`main.py`** - FastAPI application entry point
- **`api/v1/endpoints/`** - Clean API endpoints
  - `navigation.py` - Word-to-document navigation
  - `batch.py` - PDF batch processing
  - `cases.py` - Case management
  - `health.py` - System health

### Database Schema (`init-db.sql`)

#### AI-Generated Tables
- **`cases`** - Main case records with Washington State categorization
- **`parties`** - Case parties (Appellant, Respondent, etc.)
- **`attorneys`** - Legal counsel information
- **`judges`** - Normalized judge data with case relationships
- **`issues`** - Legal issues with Washington State hierarchy
- **`decisions`** - Court decisions with winner tracking
- **`citation_edges`** - Legal precedent relationships

#### RAG Tables
- **`case_chunks`** - Text chunks with embeddings (semantic search)
- **`word_dictionary`** - Unique words (lexical search)
- **`word_occurrence`** - Word positions (precise phrase matching)
- **`case_phrases`** - Legal n-grams (terminology discovery)

## 🎯 Key Features

### 1. 🤖 AI-Powered Extraction
- **Washington State Divorce Appeals Categorization**
- **Ollama + OpenAI Integration** with fallbacks
- **Structured Output** using Pydantic models
- **Comprehensive Entity Extraction** (parties, attorneys, judges, issues, decisions)

### 2. 🔍 Advanced Search & Navigation
- **Semantic Search** via vector embeddings
- **Precise Lexical Search** via word positions
- **Legal Phrase Discovery** via n-gram extraction
- **Word-to-Document Navigation** with context windows

### 3. 📊 RAG Capabilities
- **Intelligent Text Chunking** with legal section awareness
- **Multi-level Embeddings** (case-level + chunk-level)
- **Hierarchical Navigation** (word → context → chunk → document)
- **Legal Terminology Indexing**

## 🛠️ API Endpoints

### Navigation API (`/api/v1/navigation/`)
```
GET /word/{word}/occurrences              # Find word across all cases
GET /word/{word}/context/{chunk_id}       # Get context around word
GET /chunk/{chunk_id}                     # Get full chunk data
GET /chunk/{chunk_id}/adjacent            # Get surrounding chunks
GET /chunk/{chunk_id}/document            # Get complete case document
GET /word/{word}/complete-navigation      # Full word-to-doc workflow
```

### Batch Processing API (`/api/v1/batch/`)
```
POST /upload-pdfs                         # Upload PDFs for processing
GET /status/{job_id}                      # Check processing status
GET /results/{job_id}                     # Get detailed results
POST /process-single                      # Process single PDF immediately
```

### Cases API (`/api/v1/cases/`)
```
GET /                                     # List all cases
GET /{case_id}                           # Get specific case
POST /                                   # Create new case
```

## 🗄️ Database Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/law_helper

# AI Models
USE_OLLAMA=true
OLLAMA_MODEL=qwen:32b
OLLAMA_EMBED_MODEL=mxbai-embed-large
OPENAI_API_KEY=your_openai_key  # Optional fallback

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=true
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📁 Project Structure

```
law-helper/
├── app/                          # FastAPI application
│   ├── api/v1/endpoints/        # API endpoints
│   ├── services/                # Core business logic
│   ├── models/                  # SQLAlchemy models
│   ├── core/                    # Configuration
│   └── main.py                  # FastAPI app
├── batch_processor.py           # Main PDF batch processing script
├── init-db.sql                 # Database schema
├── docker-compose.yml          # Docker services
├── requirements.txt            # Python dependencies
├── docs/                       # Documentation
└── scripts/                    # Utility scripts
```

## 🔧 Development

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start database
docker-compose up -d postgres

# Initialize database
docker-compose exec postgres psql -U law_user -d law_helper -f /docker-entrypoint-initdb.d/init-db.sql
```

### Testing
```bash
# Test single PDF processing
python batch_processor.py ./test_pdfs/ --limit 1 --verbose

# Test API endpoints
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/navigation/examples
```

## 📚 Documentation

- **[Batch Processing Guide](docs/BATCH_PROCESSING_GUIDE.md)** - Detailed processing workflow
- **[Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)** - Production deployment
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - System migration procedures
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs

## 🎯 Washington State Legal Categorization

The system includes comprehensive Washington State divorce appeals categorization:

### Top-Level Categories
1. **Spousal Support / Maintenance**
2. **Child Support**
3. **Parenting Plan / Custody / Visitation**
4. **Property Division / Debt Allocation**
5. **Attorney Fees & Costs**
6. **Procedural & Evidentiary Issues**
7. **Jurisdiction & Venue**
8. **Enforcement & Contempt Orders**
9. **Modification Orders**
10. **Miscellaneous / Unclassified**

Each category includes detailed subcategories, RCW references, and legal keywords for precise classification.

## 🚀 Production Deployment

1. **Set Environment Variables** for production
2. **Configure Docker Compose** with production settings
3. **Set up SSL/TLS** for API endpoints
4. **Configure Backup Strategy** for PostgreSQL
5. **Set up Monitoring** for processing jobs
6. **Scale Ollama** for concurrent processing

## 📞 Support

For issues or questions:
1. Check the **[API Documentation](http://localhost:8000/docs)**
2. Review **[System Logs](http://localhost:8000/api/v1/health)**
3. Test with **[Example Scripts](scripts/)**

---

**Built with FastAPI, PostgreSQL, pgvector, Ollama, and comprehensive legal domain expertise.**
