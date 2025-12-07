#!/usr/bin/env python3
"""
Test script for the new Legal Case Pipeline
Run this to verify the pipeline works correctly.
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_pdf_extraction():
    """Test PDF text extraction."""
    from pipeline.pdf_extractor import PDFExtractor
    
    print("\n" + "="*60)
    print("TEST 1: PDF Extraction")
    print("="*60)
    
    extractor = PDFExtractor()
    print(f"Using LlamaParse: {extractor.using_llamaparse}")
    
    # Test with a sample PDF
    test_pdf = Path("downloads/Supreme_Court_Opinions/2025/January/102,586-6_Pub. Util. Dist. No. 1 of Snohomish County v. Stat.pdf")
    
    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        return False
    
    text, page_count = extractor.extract_text(str(test_pdf))
    
    print(f"✓ Extracted {len(text)} characters from {page_count} pages")
    print(f"✓ First 500 chars:\n{text[:500]}")
    
    return True


def test_llm_connection():
    """Test Ollama LLM connection."""
    from pipeline.llm_extractor import LLMExtractor
    
    print("\n" + "="*60)
    print("TEST 2: Ollama LLM Connection")
    print("="*60)
    
    extractor = LLMExtractor()
    
    if extractor.test_connection():
        print(f"✓ Ollama connected, model: {extractor.model}")
        return True
    else:
        print("✗ Ollama connection failed")
        return False


def test_llm_extraction():
    """Test LLM extraction on sample text."""
    from pipeline.pdf_extractor import PDFExtractor
    from pipeline.llm_extractor import LLMExtractor
    
    print("\n" + "="*60)
    print("TEST 3: LLM Extraction")
    print("="*60)
    
    # First extract PDF text
    pdf_extractor = PDFExtractor()
    test_pdf = Path("downloads/Supreme_Court_Opinions/2025/January/102,586-6_Pub. Util. Dist. No. 1 of Snohomish County v. Stat.pdf")
    
    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        return False
    
    text, _ = pdf_extractor.extract_text(str(test_pdf))
    
    # Run LLM extraction
    llm_extractor = LLMExtractor()
    result = llm_extractor.extract(text)
    
    if "error" in result:
        print(f"✗ LLM extraction failed: {result['error']}")
        return False
    
    print(f"✓ LLM extraction successful")
    print(f"  Summary: {result.get('summary', 'N/A')[:200]}...")
    print(f"  Case type: {result.get('case_type', 'N/A')}")
    print(f"  Parties: {len(result.get('parties', []))}")
    print(f"  Judges: {len(result.get('judges', []))}")
    print(f"  Issues: {len(result.get('issues', []))}")
    
    return True


def test_metadata_parsing():
    """Test CSV metadata parsing."""
    from pipeline.case_processor import CaseProcessor
    
    print("\n" + "="*60)
    print("TEST 4: Metadata CSV Parsing")
    print("="*60)
    
    processor = CaseProcessor()
    
    csv_path = Path("downloads/Supreme_Court_Opinions/metadata.csv")
    if not csv_path.exists():
        print(f"Metadata CSV not found: {csv_path}")
        return False
    
    metadata_map = processor.load_metadata_csv(str(csv_path))
    
    print(f"✓ Loaded {len(metadata_map)} cases from metadata")
    
    # Show first case
    if metadata_map:
        first_key = list(metadata_map.keys())[0]
        first_row = metadata_map[first_key]
        meta = processor.parse_metadata_row(first_row)
        
        print(f"  Sample case: {meta.case_number}")
        print(f"  Title: {meta.case_title}")
        print(f"  Court: {meta.court_level}")
        print(f"  Date: {meta.file_date}")
    
    return True


def test_full_pipeline():
    """Test the complete pipeline on a single case."""
    from pipeline.case_processor import CaseProcessor
    
    print("\n" + "="*60)
    print("TEST 5: Full Pipeline (Single Case)")
    print("="*60)
    
    processor = CaseProcessor()
    
    # Load metadata
    csv_path = Path("downloads/Supreme_Court_Opinions/metadata.csv")
    metadata_map = processor.load_metadata_csv(str(csv_path))
    
    # Find a test case
    test_pdf = Path("downloads/Supreme_Court_Opinions/2025/January/102,586-6_Pub. Util. Dist. No. 1 of Snohomish County v. Stat.pdf")
    
    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        return False
    
    # Find matching metadata
    metadata_row = None
    for case_num, row in metadata_map.items():
        if case_num in test_pdf.name:
            metadata_row = row
            break
    
    # Process the case
    case = processor.process_case(str(test_pdf), metadata_row)
    
    if case.extraction_successful:
        print(f"✓ Pipeline successful!")
        print(f"  Case: {case.metadata.case_number} - {case.metadata.case_title}")
        print(f"  Summary: {case.summary[:200]}..." if case.summary else "  Summary: N/A")
        print(f"  Parties: {[p.name for p in case.parties]}")
        print(f"  Judges: {[j.name for j in case.judges]}")
        print(f"  Issues: {len(case.issues)}")
        print(f"  Citations: {len(case.citations)}")
        return True
    else:
        print(f"✗ Pipeline failed: {case.error_message}")
        return False


def test_database_insert():
    """Test database insertion."""
    from pipeline.case_processor import CaseProcessor
    from pipeline.db_inserter import DatabaseInserter
    from pipeline.config import PipelineConfig
    
    print("\n" + "="*60)
    print("TEST 6: Database Insertion")
    print("="*60)
    
    config = PipelineConfig.from_env()
    
    # Process a case first
    processor = CaseProcessor()
    csv_path = Path("downloads/Supreme_Court_Opinions/metadata.csv")
    metadata_map = processor.load_metadata_csv(str(csv_path))
    
    test_pdf = Path("downloads/Supreme_Court_Opinions/2025/January/102,586-6_Pub. Util. Dist. No. 1 of Snohomish County v. Stat.pdf")
    
    metadata_row = None
    for case_num, row in metadata_map.items():
        if case_num in test_pdf.name:
            metadata_row = row
            break
    
    case = processor.process_case(str(test_pdf), metadata_row)
    
    if not case.extraction_successful:
        print(f"✗ Extraction failed, cannot test insert")
        return False
    
    # Insert into database
    inserter = DatabaseInserter.from_url(config.database_url)
    
    before_count = inserter.get_case_count()
    case_id = inserter.insert_case(case)
    after_count = inserter.get_case_count()
    
    if case_id:
        print(f"✓ Inserted case with ID: {case_id}")
        print(f"  Cases in DB: {before_count} → {after_count}")
        return True
    else:
        print(f"✗ Database insert failed")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("LEGAL CASE PIPELINE - TEST SUITE")
    print("="*60)
    
    tests = [
        ("PDF Extraction", test_pdf_extraction),
        ("LLM Connection", test_llm_connection),
        ("LLM Extraction", test_llm_extraction),
        ("Metadata Parsing", test_metadata_parsing),
        ("Full Pipeline", test_full_pipeline),
        # ("Database Insert", test_database_insert),  # Uncomment to test DB
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} raised exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{len(results)} tests passed")
    
    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
