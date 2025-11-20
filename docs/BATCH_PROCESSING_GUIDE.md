# 🦙 Batch PDF Processing Guide - Ollama Only

This guide helps you process multiple PDFs using **only Ollama** (no OpenAI dependencies) with full AI extraction, word indexing, and embeddings.

## 🚀 Quick Start

```bash
# 1. Setup and verify environment
python setup_ollama_processing.py

# 2. Process all PDFs in a folder
python batch_process_pdfs.py /path/to/your/pdfs

# 3. Process with specific model
python batch_process_pdfs.py /path/to/your/pdfs --ollama-model llama3.1:latest

# 4. Verbose mode with report
python batch_process_pdfs.py /path/to/your/pdfs --verbose --output-report results.json
```

## 📋 Prerequisites

### 1. Ollama Installation
```bash
# Install Ollama from https://ollama.ai/
curl -fsSL https://ollama.ai/install.sh | sh

# Verify installation
ollama --version
```

### 2. Required Models
```bash
# Download AI extraction model (4.3GB)
ollama pull llama3.3:latest

# Download embedding model (669MB)
ollama pull mxbai-embed-large
```

### 3. Database Running
```bash
# Start the legal database
docker compose up -d
```

## 🔧 Configuration

### Environment Setup
The system automatically configures itself for Ollama-only mode:

```bash
# These are set automatically by the script:
USE_OLLAMA=true
OLLAMA_MODEL=llama3.3:latest
OLLAMA_EMBED_MODEL=mxbai-embed-large
# OPENAI_API_KEY is disabled
```

## 📖 Usage Examples

### Basic Processing
```bash
# Process all PDFs in current directory
python batch_process_pdfs.py ./

# Process PDFs in specific folder
python batch_process_pdfs.py /home/user/legal_documents/
```

### Advanced Options
```bash
# Use different Ollama model
python batch_process_pdfs.py ./pdfs --ollama-model llama3.1:latest

# Verbose logging
python batch_process_pdfs.py ./pdfs --verbose

# Save processing report
python batch_process_pdfs.py ./pdfs --output-report processing_report.json
```

### Recursive Processing
The script automatically finds PDFs in all subdirectories:
```
your_folder/
├── case1.pdf          ✅ Processed
├── subfolder/
│   ├── case2.pdf      ✅ Processed
│   └── case3.pdf      ✅ Processed
└── documents/
    └── case4.pdf      ✅ Processed
```

## 🎯 What Gets Processed

For each PDF, the system performs:

### 🤖 AI Extraction (Ollama)
- **Cases**: Title, court, dates, summary
- **Parties**: Names, legal roles, personal roles
- **Attorneys**: Names, firms, addresses
- **Judges**: Names and roles (Author/Concurring/Dissenting)
- **Issues**: Legal issues with AI classification
- **Decisions**: Outcomes with reasoning
- **Citations**: Precedent cases and relationships

### 📝 Text Processing
- **Chunking**: Semantic text segmentation
- **Word Indexing**: Precise word position tracking
- **Embeddings**: Vector embeddings for semantic search

### 🗄️ Database Storage
All data is stored in your PostgreSQL database with:
- **17 Tables**: Complete legal schema
- **Relationships**: Proper foreign keys and constraints
- **Search Indexes**: Vector, full-text, and trigram indexes

## 📊 Output & Monitoring

### Real-time Progress
```
📄 Processing PDF 3/15: case_smith_v_jones.pdf
========================================
📖 Reading PDF file...
   File size: 2.34 MB
🤖 Starting AI extraction and database ingestion...
📊 Processing Results:
   Case ID: a8f31937-5cb5-4148-9cde-a079113576f4
   Text Pages: 12
   Text Chunks: 45
   Words Indexed: 2,847
   AI Entities: 23
   Embeddings: 46
   Processing Time: 34.2s
✅ Successfully processed: case_smith_v_jones.pdf
```

### Final Report
```
📈 FINAL PROCESSING REPORT
======================================
Total Files: 15
Successfully Processed: 14
Failed: 1
Success Rate: 93.3%
Total Duration: 12.4 minutes
Average Time per File: 49.8s
```

## 🔍 Verification

### Check Database Contents
```bash
# Connect to database
docker exec -it legal_ai_postgres psql -U legal_user -d legal_ai

# Check processed cases
SELECT case_id, title, court FROM cases ORDER BY created_at DESC LIMIT 5;

# Check word indexing
SELECT COUNT(*) as total_words FROM word_dictionary;
SELECT COUNT(*) as total_positions FROM word_occurrence;

# Check embeddings
SELECT COUNT(*) as cases_with_embeddings 
FROM cases WHERE full_embedding IS NOT NULL;
```

### Search Capabilities
After processing, you can search using:
- **Semantic Search**: Vector similarity on case content
- **Phrase Search**: Exact phrase matching using word positions
- **Entity Search**: Search by parties, attorneys, judges
- **Citation Search**: Find cases that cite specific precedents

## ⚠️ Troubleshooting

### Common Issues

**Ollama Connection Failed**
```bash
# Check if Ollama is running
ollama list

# If not running, start it
ollama serve
```

**Model Not Found**
```bash
# Pull required models
ollama pull llama3.3:latest
ollama pull mxbai-embed-large
```

**Database Connection Failed**
```bash
# Start database containers
docker compose up -d

# Check status
docker ps
```

**Memory Issues**
```bash
# For large batches, process in smaller chunks
python batch_process_pdfs.py ./batch1/
python batch_process_pdfs.py ./batch2/
```

### Performance Tips

1. **Model Size vs Speed**:
   - `llama3.3:latest` (4.3GB) - High quality, slower
   - `llama3.1:latest` (4.7GB) - Alternative option
   - `llama3:latest` (4.7GB) - Stable version

2. **Batch Size**: Process 10-20 files at a time for optimal performance

3. **System Resources**: Ensure sufficient RAM (8GB+ recommended)

## 🎯 Next Steps

After batch processing:

1. **Verify Results**: Check database contents and search functionality
2. **Build Search Interface**: Use the API endpoints to create search tools
3. **Analytics**: Use the materialized views for legal analytics
4. **Backup**: Export your processed data for safekeeping

## 🤝 Support

If you encounter issues:
1. Run the setup script: `python setup_ollama_processing.py`
2. Check the verbose logs: `--verbose` flag
3. Review the error report: `--output-report errors.json`
4. Verify all prerequisites are met

Happy processing! 🦙⚖️