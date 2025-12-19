#!/usr/bin/env python
"""
Run Pipeline - CLI entry point for the case ingestion pipeline.

Usage:
    # Process a single case
    python -m pipeline.run_pipeline --pdf path/to/case.pdf --csv path/to/metadata.csv --row 21
    
    # Process a batch
    python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv downloads/Supreme_Court_Opinions/metadata.csv
    
    # Production batch with progress tracking (recommended for overnight runs)
    python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv metadata.csv --job-name my_job
    
    # Resume interrupted job
    python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv metadata.csv --resume logs/checkpoint_my_job.json
    
    # Retry failed files
    python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --csv metadata.csv --retry-failed logs/failed_my_job.csv
    
    # Control RAG options
    python -m pipeline.run_pipeline --pdf path/to/case.pdf --chunk-embeddings important --phrase-filter relaxed
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.config import Config
from pipeline.case_processor import CaseProcessor
from pipeline.db_inserter import DatabaseInserter
from pipeline.progress_tracker import ProgressTracker, load_failed_files_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_single_case(args):
    """Process a single PDF file."""
    logger.info(f"Processing single case: {args.pdf}")
    
    # Create PDF extractor with specified mode
    from .pdf_extractor import PDFExtractor
    pdf_extractor = PDFExtractor(mode=args.pdf_extractor)
    
    # Load metadata if provided
    metadata_row = None
    if args.csv and args.row is not None:
        processor = CaseProcessor(pdf_extractor=pdf_extractor)
        metadata_map = processor.load_metadata_csv(args.csv)
        
        # Find by row number (1-indexed in the CSV means index in the list)
        csv_rows = list(metadata_map.values())
        if 0 < args.row <= len(csv_rows):
            # Get by case_number key
            keys = list(metadata_map.keys())
            if args.row <= len(keys):
                case_key = keys[args.row - 1]
                metadata_row = metadata_map[case_key]
                logger.info(f"Using metadata for case: {case_key}")
        else:
            logger.warning(f"Row {args.row} not found in CSV, processing without metadata")
    
    # Process the case
    processor = CaseProcessor(pdf_extractor=pdf_extractor)
    case = processor.process_case(args.pdf, metadata_row)
    
    if not case.extraction_successful:
        logger.error(f"Extraction failed: {case.error_message}")
        return None
    
    # Insert into database
    db_url = Config.get_database_url()
    inserter = DatabaseInserter.from_url(db_url, enable_rag=args.enable_rag)
    
    # Configure RAG options
    if args.enable_rag:
        inserter.configure_rag(
            chunk_embedding_mode=args.chunk_embeddings,
            phrase_filter_mode=args.phrase_filter
        )
    
    case_id = inserter.insert_case(case)
    
    if case_id:
        logger.info(f"Successfully inserted case with ID: {case_id}")
        print(f"\n✓ Case {case_id} inserted successfully")
        print(f"  Title: {case.metadata.case_title if case.metadata else 'Unknown'}")
        print(f"  Parties: {len(case.parties)}")
        print(f"  Judges: {len(case.judges)}")
        print(f"  Citations: {len(case.citations)}")
        print(f"  Issues: {len(case.issues)}")
        if args.enable_rag:
            print(f"  RAG processing: enabled (chunks={args.chunk_embeddings}, phrases={args.phrase_filter})")
    else:
        logger.error("Insert failed")
        print("\n✗ Insert failed - check logs")
    
    return case_id


def process_batch(args):
    """Process a batch of PDF files with progress tracking."""
    logger.info(f"Processing batch from: {args.pdf_dir}")
    
    # Initialize progress tracker
    tracker = ProgressTracker(
        output_dir="logs",
        job_name=args.job_name
    )
    
    # Load checkpoint if resuming
    if args.resume:
        if not tracker.load_checkpoint(args.resume):
            logger.warning(f"Could not load checkpoint from {args.resume}, starting fresh")
    
    # Determine number of workers
    max_workers = 1 if args.sequential else args.workers
    parallel = not args.sequential and args.workers > 1
    
    # Create PDF extractor with specified mode
    from .pdf_extractor import PDFExtractor
    pdf_extractor = PDFExtractor(mode=args.pdf_extractor)
    
    processor = CaseProcessor(
        pdf_extractor=pdf_extractor,
        max_workers=max_workers
    )
    
    # Get list of PDF files to process
    pdf_dir = Path(args.pdf_dir)
    if args.retry_failed:
        # Only retry specific failed files
        all_pdf_files = load_failed_files_csv(args.retry_failed)
        # Filter to only existing files
        all_pdf_files = [f for f in all_pdf_files if Path(f).exists()]
        logger.info(f"Retrying {len(all_pdf_files)} failed files from {args.retry_failed}")
    else:
        # Recursive search for PDFs
        all_pdf_files = list(pdf_dir.rglob("*.pdf"))
        all_pdf_files = [str(p) for p in all_pdf_files]
    
    # Apply limit if specified
    if args.limit:
        all_pdf_files = all_pdf_files[:args.limit]
    
    # Filter out already-processed files
    pdf_files = tracker.get_unprocessed_files(all_pdf_files)
    
    # Start job tracking
    tracker.start_job(len(all_pdf_files))
    
    if not pdf_files:
        logger.info("All files already processed!")
        tracker.finish_job()
        return {'success': 0, 'failed': 0, 'duplicates': 0, 'skipped': len(all_pdf_files)}
    
    logger.info(f"Processing {len(pdf_files)} remaining files ({len(all_pdf_files) - len(pdf_files)} already done)")
    
    # Load metadata CSV for lookup
    metadata_map = {}
    if args.csv:
        metadata_map = processor.load_metadata_csv(args.csv)
    
    # Process cases with progress tracking
    cases = processor.process_batch(
        pdf_dir=args.pdf_dir,
        metadata_csv=args.csv,
        limit=None,  # We already filtered files
        parallel=parallel,
        pdf_files=pdf_files  # Pass specific files to process
    )
    
    # Track extraction results - mark successes AND failures
    successful = []
    for case in cases:
        if case.extraction_successful:
            # Mark extraction success immediately (separate from insert)
            # This allows recovery if insert fails later
            tracker.mark_extraction_success(case.metadata.pdf_filename or "")
            successful.append(case)
        else:
            tracker.mark_failed(
                file_path=case.metadata.pdf_filename or "",
                error=case.error_message or "Unknown extraction error",
                stage="extraction",
                metadata_row=None
            )
    
    logger.info(f"[EXTRACTION COMPLETE] {len(successful)} extracted, {len(cases) - len(successful)} failed")
    print(f"\n>>> Starting INSERT phase for {len(successful)} cases with {max_workers} workers...", flush=True)
    
    # Insert all successful cases with per-case tracking
    db_url = Config.get_database_url()
    inserter = DatabaseInserter.from_url(db_url, enable_rag=args.enable_rag)
    
    # Configure RAG options
    if args.enable_rag:
        inserter.configure_rag(
            chunk_embedding_mode=args.chunk_embeddings,
            phrase_filter_mode=args.phrase_filter
        )
    
    # Insert with progress tracking callback
    def on_insert_result(case, case_id, error, was_duplicate):
        """Callback for each insert result."""
        file_path = case.metadata.pdf_filename or ""
        if case_id:
            tracker.mark_success(file_path, case_id, was_duplicate)
        else:
            tracker.mark_failed(file_path, error or "Unknown insert error", stage="insert")
    
    results = inserter.insert_batch(
        successful, 
        max_workers=max_workers,
        progress_callback=on_insert_result
    )
    
    # Finish job
    tracker.finish_job()
    
    # Force flush to ensure output is visible
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    print(f"\n{'='*50}", flush=True)
    print(f"Batch Processing Complete", flush=True)
    print(f"{'='*50}", flush=True)
    print(f"  Total PDFs: {len(all_pdf_files)}", flush=True)
    print(f"  Extracted: {len(successful)}", flush=True)
    print(f"  Inserted: {results['success']}", flush=True)
    print(f"  Duplicates Updated: {results.get('duplicates', 0)}", flush=True)
    print(f"  Failed: {results['failed']}", flush=True)
    if args.enable_rag:
        print(f"  RAG mode: chunks={args.chunk_embeddings}, phrases={args.phrase_filter}", flush=True)
    
    # Final flush before returning
    sys.stdout.flush()
    sys.stderr.flush()
    
    return results


def verify_case(args):
    """Verify all columns for a specific case."""
    from sqlalchemy import create_engine, text
    
    db_url = Config.get_database_url()
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Get case data
        result = conn.execute(text("""
            SELECT 
                case_id, title, court_level, court, district, county,
                docket_number, source_docket_number, trial_judge,
                appeal_published_date, published, summary,
                source_url, case_info_url,
                overall_case_outcome, appeal_outcome,
                winner_legal_role, winner_personal_role,
                opinion_type, publication_status,
                decision_year, decision_month,
                case_type, source_file,
                court_id, case_type_id, stage_type_id,
                extraction_timestamp, processing_status,
                LENGTH(full_text) as text_length,
                CASE WHEN full_embedding IS NOT NULL THEN 1024 ELSE 0 END as embedding_dim
            FROM cases WHERE case_id = :case_id
        """), {'case_id': args.case_id})
        
        row = result.fetchone()
        
        if not row:
            print(f"Case {args.case_id} not found")
            return
        
        print(f"\n{'='*60}")
        print(f"Case {args.case_id} Verification")
        print(f"{'='*60}")
        
        # Display all columns
        columns = result.keys()
        for col, val in zip(columns, row):
            if val is not None:
                print(f"  ✓ {col}: {val}")
            else:
                print(f"  ○ {col}: NULL")
        
        # Get related entity counts
        counts = {}
        for table, id_col in [
            ('parties', 'case_id'),
            ('attorneys', 'case_id'),
            ('case_judges', 'case_id'),
            ('citation_edges', 'source_case_id'),
            ('statute_citations', 'case_id'),
            ('issues_decisions', 'case_id'),
            ('case_chunks', 'case_id'),
            ('case_sentences', 'chunk_id'),
            ('case_phrases', 'case_id'),
        ]:
            try:
                if table == 'case_sentences':
                    q = text("""
                        SELECT COUNT(*) FROM case_sentences cs
                        JOIN case_chunks cc ON cs.chunk_id = cc.id
                        WHERE cc.case_id = :case_id
                    """)
                else:
                    q = text(f"SELECT COUNT(*) FROM {table} WHERE {id_col} = :case_id")
                count = conn.execute(q, {'case_id': args.case_id}).scalar()
                counts[table] = count
            except:
                counts[table] = "N/A"
        
        print(f"\n{'='*60}")
        print("Related Entities")
        print(f"{'='*60}")
        for table, count in counts.items():
            print(f"  {table}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description='Legal Case Ingestion Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single case
  python -m pipeline.run_pipeline --pdf downloads/Supreme_Court_Opinions/123456.pdf --csv downloads/Supreme_Court_Opinions/metadata.csv --row 21

  # Process batch (first 10 cases)
  python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --limit 10

  # Production batch with job name (for overnight runs)
  python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --job-name overnight_run

  # Resume interrupted job
  python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --resume logs/checkpoint_overnight_run.json

  # Retry failed files
  python -m pipeline.run_pipeline --batch --pdf-dir downloads/Supreme_Court_Opinions --retry-failed logs/failed_overnight_run.csv

  # Process with custom RAG settings
  python -m pipeline.run_pipeline --pdf case.pdf --chunk-embeddings important --phrase-filter relaxed

  # Verify case insertion
  python -m pipeline.run_pipeline --verify --case-id 21
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--batch', action='store_true', help='Process batch of PDFs')
    mode_group.add_argument('--verify', action='store_true', help='Verify case data')
    
    # Input arguments
    parser.add_argument('--pdf', type=str, help='Path to single PDF file')
    parser.add_argument('--pdf-dir', type=str, help='Directory with PDF files (for batch)')
    parser.add_argument('--csv', type=str, help='Path to metadata CSV')
    parser.add_argument('--row', type=int, help='Row number in CSV (1-indexed)')
    parser.add_argument('--limit', type=int, help='Limit number of files in batch')
    parser.add_argument('--case-id', type=int, help='Case ID for verification')
    
    # Progress tracking arguments (for production batch runs)
    parser.add_argument(
        '--job-name',
        type=str,
        help='Job name for checkpoint/log files (default: auto-generated timestamp)'
    )
    parser.add_argument(
        '--resume',
        type=str,
        metavar='CHECKPOINT',
        help='Resume from checkpoint file (e.g., logs/checkpoint_my_job.json)'
    )
    parser.add_argument(
        '--retry-failed',
        type=str,
        metavar='CSV',
        help='Retry failed files from CSV (e.g., logs/failed_my_job.csv)'
    )
    
    # Processing options
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers for batch processing (default: 4)'
    )
    parser.add_argument(
        '--sequential',
        action='store_true',
        help='Force sequential processing (1 worker)'
    )
    parser.add_argument(
        '--pdf-extractor',
        type=str,
        choices=['pdfplumber', 'llamaparse', 'auto'],
        default='pdfplumber',
        help='PDF extraction method: pdfplumber (default, fast), llamaparse (OCR), auto (try llamaparse first)'
    )
    
    # RAG options
    parser.add_argument(
        '--enable-rag', 
        action='store_true', 
        default=True,
        help='Enable RAG processing (default: True)'
    )
    parser.add_argument(
        '--no-rag',
        action='store_true',
        help='Disable RAG processing (insert case only)'
    )
    parser.add_argument(
        '--chunk-embeddings',
        type=str,
        choices=['all', 'important', 'none'],
        default='all',
        help='Chunk embedding mode: all (default), important (ANALYSIS/HOLDING/FACTS only), none'
    )
    parser.add_argument(
        '--phrase-filter',
        type=str,
        choices=['strict', 'relaxed'],
        default='strict',
        help='Phrase filtering mode: strict (legal terms only, default), relaxed (all meaningful phrases)'
    )
    
    args = parser.parse_args()
    
    # Handle --no-rag flag
    if args.no_rag:
        args.enable_rag = False
    
    # Route to appropriate handler
    if args.verify:
        if not args.case_id:
            parser.error("--verify requires --case-id")
        verify_case(args)
    elif args.batch:
        if not args.pdf_dir:
            parser.error("--batch requires --pdf-dir")
        process_batch(args)
    else:
        if not args.pdf:
            parser.error("Single case processing requires --pdf")
        process_single_case(args)


if __name__ == '__main__':
    main()
