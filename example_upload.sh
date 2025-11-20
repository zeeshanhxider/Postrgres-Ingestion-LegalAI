#!/bin/bash

# Enhanced script to upload legal cases with AI extraction
# Usage: ./example_upload.sh [pdf_file] or ./example_upload.sh excel [excel_file]

echo "🧠 Enhanced Legal Case Upload with AI Extraction"
echo "================================================"

if [ "$1" = "excel" ]; then
    # Excel upload mode
    EXCEL_FILE="$2"
    
    if [ -z "$EXCEL_FILE" ]; then
        echo "Usage: $0 excel <path_to_excel_file>"
        echo "Example: $0 excel /home/user/documents/cases.xlsx"
        exit 1
    fi
    
    if [ ! -f "$EXCEL_FILE" ]; then
        echo "Error: File '$EXCEL_FILE' does not exist"
        exit 1
    fi
    
    echo "📊 Uploading Excel file with AI extraction: $EXCEL_FILE"
    
    curl -X POST "http://localhost:8000/api/v1/excel/upload-excel" \
      -F "excel_file=@$EXCEL_FILE" \
      -F 'processing_options={
        "enable_ai_extraction": true,
        "process_all_sheets": true,
        "max_cases": 10
      }' \
      -H "accept: application/json" \
      -v

else
    # PDF upload mode
    PDF_FILE="$1"
    
    if [ -z "$PDF_FILE" ]; then
        echo "Usage: $0 <path_to_pdf_file>"
        echo "   OR: $0 excel <path_to_excel_file>"
        echo ""
        echo "Examples:"
        echo "  $0 /home/user/documents/case.pdf"
        echo "  $0 excel /home/user/documents/cases.xlsx"
        exit 1
    fi
    
    if [ ! -f "$PDF_FILE" ]; then
        echo "Error: File '$PDF_FILE' does not exist"
        exit 1
    fi
    
    echo "📄 Uploading PDF with AI extraction: $PDF_FILE"
    
    # Upload PDF with enhanced AI extraction
    curl -X POST "http://localhost:8000/api/v1/cases/upload" \
      -F "pdf_file=@$PDF_FILE" \
      -F 'metadata={
        "title": "Enhanced AI Test Case",
        "court": "Court of Appeals of Washington",
        "docket_number": "AI-TEST-001",
        "filing_date": "2024-03-07",
        "enable_ai_extraction": true
      }' \
      -H "accept: application/json" \
      -v
fi

echo ""
echo "🎉 Upload completed with AI extraction!"
echo ""
echo "✨ What was processed:"
echo "   🧠 AI extraction of legal entities (parties, attorneys, issues)"
echo "   📝 Text chunking for semantic search"
echo "   🔍 Word-level indexing for exact phrase search"
echo "   💾 Transactional database storage"
echo ""
echo "🔍 Test phrase search:"
echo "curl -X GET \"http://localhost:8000/api/v1/cases/search/phrase?query=contract%20breach&limit=5\""
echo ""
echo "📊 Check database stats:"
echo "curl -X GET \"http://localhost:8000/api/v1/cases/stats\""