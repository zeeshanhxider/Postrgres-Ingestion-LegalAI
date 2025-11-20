# Legal Case Processing System

## 🎯 **CLEAN & ORGANIZED CODEBASE**

This system provides complete legal case processing with AI extraction and comprehensive RAG capabilities.

## 📁 **FILE ORGANIZATION**

### **Core Services** (`app/services/`)
- **`ai_extractor.py`** - AI extraction service (Ollama + OpenAI)
- **`case_ingestor.py`** - Main case processing orchestrator
- **`database_inserter.py`** - Database insertion service
- **`models.py`** - Pydantic models for all entities
- **`prompts.py`** - AI extraction prompts

### **RAG Services** (`app/services/`)
- **`word_processor.py`** - Word indexing for precise search
- **`phrase_extractor.py`** - N-gram phrase extraction
- **`embedding_service.py`** - Vector embedding generation

### **Processing**
- **`batch_processor.py`** - Batch PDF processing script

## 🏗️ **SYSTEM ARCHITECTURE**

### **1. AI Extraction**
```python
from app.services.ai_extractor import extract_case_data

# Extract legal case data using Ollama or OpenAI
result = extract_case_data(case_text, case_info)
```

### **2. Case Processing**
```python
from app.services.case_ingestor import LegalCaseIngestor

ingestor = LegalCaseIngestor(database_engine)
result = ingestor.ingest_pdf_case(pdf_content, metadata)
```

### **3. Batch Processing**
```bash
# Process all PDFs in directory
python batch_processor.py ./case-pdfs/

# Process with limit
python batch_processor.py ./case-pdfs/ --limit 10
```

## 📊 **DATA MODELS**

All entities use clean, descriptive models:

- **`CaseModel`** - Case metadata
- **`JudgeModel`** - Appeals court judges  
- **`AttorneyModel`** - Legal attorneys
- **`PartyModel`** - Case parties with roles
- **`IssueModel`** - Legal issues
- **`DecisionModel`** - Court decisions
- **`PrecedentModel`** - Legal precedents

## 🔍 **RAG CAPABILITIES**

### **Search Types**
1. **Vector Search** - Semantic similarity via embeddings
2. **Phrase Search** - Exact legal terminology matching
3. **Word Search** - Precise word occurrence tracking
4. **Entity Search** - Find by party, attorney, judge names
5. **Full-Text Search** - PostgreSQL tsvector search

### **Database Tables**
- **Core**: `cases`, `parties`, `attorneys`, `judges`, `enhanced_issues`, `decisions`, `citation_edges`
- **RAG**: `case_chunks`, `word_dictionary`, `word_occurrence`, `case_phrases`

## 🚀 **KEY FEATURES**

### **✅ Proven AI Extraction**
- Simple, effective prompts that work
- Reliable Ollama integration with OpenAI fallback
- Clean validation without over-engineering

### **✅ Comprehensive Database**
- All entities properly inserted
- Source file traceability
- Winner data extraction
- Normalized relationships

### **✅ RAG-Ready**
- Document chunking for semantic search
- Word-level indexing for precise queries
- Legal phrase extraction
- Vector embeddings for similarity

### **✅ Production Ready**
- Clean error handling
- Comprehensive logging
- Batch processing capabilities
- Database transaction safety

## 🎯 **USAGE EXAMPLES**

### **Process Single Case**
```python
from app.services.case_ingestor import LegalCaseIngestor
from app.database import engine

ingestor = LegalCaseIngestor(engine)
result = ingestor.ingest_pdf_case(
    pdf_content=pdf_bytes,
    metadata={'title': 'Case Name', 'court': 'Appeals Court'},
    source_file_info={'filename': 'case.pdf', 'file_path': '/path/to/case.pdf'}
)
```

### **Batch Process PDFs**
```bash
# Basic usage
python batch_processor.py ./case-pdfs/

# With options
python batch_processor.py ./case-pdfs/ --limit 50 --verbose
```

## 🔧 **CONFIGURATION**

### **Environment Variables**
```bash
USE_OLLAMA=true                    # Use Ollama for extraction
OLLAMA_MODEL=qwen:32b             # Ollama model
OLLAMA_EMBED_MODEL=mxbai-embed-large  # Embedding model
OPENAI_API_KEY=sk-...             # OpenAI fallback
DATABASE_URL=postgresql://...      # Database connection
```

## 📈 **PERFORMANCE**

- **AI Extraction**: Proven reliable approach
- **Batch Processing**: ~2-5 cases/minute (depending on size)
- **Database**: Optimized with proper indexes
- **RAG**: Multiple search methods for flexibility

## 🎉 **READY FOR**

- **Production deployment**
- **MCP integration** 
- **RAG applications**
- **Legal search systems**
- **Case analysis tools**

This system combines the reliability of proven approaches with the power of comprehensive RAG capabilities!
