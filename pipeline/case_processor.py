"""
Case Processor - Orchestrates the extraction pipeline
Combines metadata (CSV) + PDF extraction + LLM extraction
"""

import csv
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dateutil import parser as date_parser
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .models import CaseMetadata, ExtractedCase
from .pdf_extractor import PDFExtractor
from .llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)

# Thread-local storage for per-thread extractors
_thread_local = threading.local()

# Washington State Counties (official list - 39 counties)
WASHINGTON_COUNTIES = {
    'adams', 'asotin', 'benton', 'chelan', 'clark', 'clallam', 'columbia',
    'cowlitz', 'douglas', 'ferry', 'franklin', 'garfield', 'grant',
    'grays harbor', 'island', 'jefferson', 'king', 'kitsap', 'kittitas',
    'klickitat', 'lewis', 'lincoln', 'mason', 'okanogan', 'pacific',
    'pend oreille', 'pierce', 'san juan', 'skagit', 'skamania',
    'snohomish', 'spokane', 'stevens', 'thurston', 'wahkiakum',
    'walla walla', 'whatcom', 'whitman', 'yakima'
}


def extract_county_from_text(text: str) -> Optional[str]:
    """
    Extract county name from case text using regex pattern matching.
    Searches against official Washington State counties list.
    
    Args:
        text: Full case text (not truncated)
        
    Returns:
        County name (title case) or None
    """
    # Search first 15000 chars where county info typically appears
    search_text = text[:15000].lower()
    
    # Try each county with various patterns
    for county in WASHINGTON_COUNTIES:
        patterns = [
            rf'\b{county} county superior court\b',
            rf'\bappeal from {county} county\b',
            rf'\bfrom {county} county superior court\b',
            rf'\bin {county} county\b',
            rf'\bof {county} county\b',
            rf'\b{county} county\b'
        ]
        
        for pattern in patterns:
            if re.search(pattern, search_text):
                # Return proper title case
                return county.title()
    
    return None


class CaseProcessor:
    """
    Main processor that orchestrates the full extraction pipeline.
    
    Pipeline:
    1. Load metadata from CSV
    2. Extract text from PDF using LlamaParse
    3. Extract structured data using LLM (Ollama)
    4. Combine metadata + LLM extraction
    """
    
    def __init__(
        self,
        pdf_extractor: Optional[PDFExtractor] = None,
        llm_extractor: Optional[LLMExtractor] = None,
        max_workers: int = 4
    ):
        """
        Initialize the case processor.
        
        Args:
            pdf_extractor: PDFExtractor instance (created if not provided)
            llm_extractor: LLMExtractor instance (created if not provided)
            max_workers: Number of parallel workers for batch processing
        """
        self.pdf_extractor = pdf_extractor or PDFExtractor()
        self.llm_extractor = llm_extractor or LLMExtractor()
        self.max_workers = max_workers
    
    def load_metadata_csv(self, csv_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Load metadata CSV and index by case_number.
        
        Args:
            csv_path: Path to metadata.csv
            
        Returns:
            Dictionary mapping case_number -> row data
        """
        metadata_map = {}
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                case_number = row.get('case_number', '').strip()
                if case_number:
                    metadata_map[case_number] = row
        
        logger.info(f"Loaded {len(metadata_map)} cases from metadata CSV")
        return metadata_map
    
    def parse_metadata_row(self, row: Dict[str, Any]) -> CaseMetadata:
        """
        Parse a CSV row into CaseMetadata dataclass.
        
        Args:
            row: Dictionary from CSV row
            
        Returns:
            CaseMetadata object
        """
        metadata = CaseMetadata()
        
        # Direct string fields
        metadata.opinion_type = row.get('opinion_type', '').strip()
        metadata.publication_status = row.get('publication_status', '').strip()
        metadata.month = row.get('month', '').strip()
        metadata.case_number = row.get('case_number', '').strip()
        metadata.division = row.get('division', '').strip()
        metadata.case_title = row.get('case_title', '').strip()
        metadata.file_contains = row.get('file_contains', '').strip()
        metadata.case_info_url = row.get('case_info_url', '').strip()
        metadata.pdf_url = row.get('pdf_url', '').strip()
        metadata.pdf_filename = row.get('pdf_filename', '').strip()
        metadata.download_status = row.get('download_status', '').strip()
        
        # Parse year
        year_str = row.get('year', '').strip()
        if year_str:
            try:
                metadata.year = int(year_str)
            except ValueError:
                pass
        
        # Parse file_date (e.g., "Jan. 16, 2025")
        file_date_str = row.get('file_date', '').strip()
        if file_date_str:
            try:
                parsed = date_parser.parse(file_date_str)
                metadata.file_date = parsed.date()
            except:
                pass
        
        # Parse scraped_at timestamp
        scraped_at_str = row.get('scraped_at', '').strip()
        if scraped_at_str:
            try:
                metadata.scraped_at = date_parser.parse(scraped_at_str)
            except:
                pass
        
        # Derive court_level from opinion_type (keep human-readable)
        opinion_type_lower = metadata.opinion_type.lower()
        if 'supreme' in opinion_type_lower:
            metadata.court_level = 'Supreme Court'
        elif 'appeals' in opinion_type_lower or 'appellate' in opinion_type_lower:
            metadata.court_level = 'Court of Appeals'
        else:
            metadata.court_level = metadata.opinion_type or 'Unknown'
        
        return metadata
    
    def process_case(
        self,
        pdf_path: str,
        metadata_row: Optional[Dict[str, Any]] = None
    ) -> ExtractedCase:
        """
        Process a single case PDF with optional metadata.
        
        Args:
            pdf_path: Path to the PDF file
            metadata_row: Optional metadata from CSV
            
        Returns:
            ExtractedCase with all extracted data
        """
        pdf_path = Path(pdf_path)
        logger.info(f"Processing case: {pdf_path.name}")
        
        # Initialize result
        case = ExtractedCase()
        
        # ALWAYS set pdf_filename from the actual file path
        case.metadata.pdf_filename = pdf_path.name
        
        try:
            # Step 1: Parse metadata if provided
            if metadata_row:
                case.metadata = self.parse_metadata_row(metadata_row)
                # Ensure pdf_filename is set even if CSV doesn't have it
                if not case.metadata.pdf_filename:
                    case.metadata.pdf_filename = pdf_path.name
                logger.info(f"  Metadata: {case.metadata.case_number} - {case.metadata.case_title}")
            else:
                # No CSV metadata - try to extract basic info from filename
                # Format: "39300-3_III.pdf" -> case_number="39300-3", division="III"
                stem = pdf_path.stem  # e.g., "39300-3_III"
                if '_' in stem:
                    parts = stem.rsplit('_', 1)
                    case.metadata.case_number = parts[0]
                    case.metadata.division = parts[1] if len(parts) > 1 else ""
                else:
                    case.metadata.case_number = stem
                logger.warning(f"  No CSV metadata found for {pdf_path.name} - using filename info")
            
            # Step 2: Extract text from PDF
            logger.info("  Extracting PDF text...")
            full_text, page_count = self.pdf_extractor.extract_text(str(pdf_path))
            case.full_text = full_text
            case.page_count = page_count
            logger.info(f"  Extracted {len(full_text)} chars from {page_count} pages")
            
            if not full_text or len(full_text.strip()) < 100:
                raise ValueError("PDF text extraction returned insufficient content")
            
            # Step 2.5: Extract county from full text (before LLM truncation)
            extracted_county = extract_county_from_text(full_text)
            if extracted_county:
                logger.info(f"  Pre-extracted county: {extracted_county}")
            
            # Step 3: Extract structured data using LLM
            logger.info("  Running LLM extraction...")
            llm_result = self.llm_extractor.extract(full_text)
            
            # Step 4: Build case from LLM result
            llm_case = self.llm_extractor.build_extracted_case(llm_result)
            
            # Merge LLM extraction into our case
            case.summary = llm_case.summary
            case.case_type = llm_case.case_type
            # Use pre-extracted county (from full text) if available, otherwise LLM result
            case.county = extracted_county or llm_case.county
            case.trial_court = llm_case.trial_court
            case.trial_judge = llm_case.trial_judge
            case.source_docket_number = llm_case.source_docket_number
            case.appeal_outcome = llm_case.appeal_outcome
            case.outcome_detail = llm_case.outcome_detail
            case.winner_legal_role = llm_case.winner_legal_role
            case.winner_personal_role = llm_case.winner_personal_role
            case.parties = llm_case.parties
            case.attorneys = llm_case.attorneys
            case.judges = llm_case.judges
            case.citations = llm_case.citations
            case.statutes = llm_case.statutes
            case.issues = llm_case.issues
            case.extraction_timestamp = datetime.now()
            case.llm_model = llm_case.llm_model
            case.extraction_successful = llm_case.extraction_successful
            case.error_message = llm_case.error_message
            
            logger.info(f"  Extraction complete: {len(case.parties)} parties, "
                       f"{len(case.judges)} judges, {len(case.issues)} issues")
            
            return case
            
        except Exception as e:
            logger.error(f"  Processing failed: {e}")
            case.extraction_successful = False
            case.error_message = str(e)
            case.extraction_timestamp = datetime.now()
            return case
    
    def process_batch(
        self,
        pdf_dir: str,
        metadata_csv: Optional[str] = None,
        limit: Optional[int] = None,
        parallel: bool = True,
        pdf_files: Optional[List[str]] = None
    ) -> List[ExtractedCase]:
        """
        Process a batch of PDF files (with optional parallel processing).
        
        Args:
            pdf_dir: Directory containing PDF files
            metadata_csv: Path to metadata CSV (optional)
            limit: Maximum number of files to process
            parallel: Use parallel processing (default True)
            pdf_files: Specific list of PDF file paths to process (overrides pdf_dir scan)
            
        Returns:
            List of ExtractedCase objects
        """
        pdf_dir = Path(pdf_dir)
        
        # Load metadata if provided
        metadata_map = {}
        if metadata_csv:
            metadata_map = self.load_metadata_csv(metadata_csv)
        
        # Use provided pdf_files list or scan directory
        if pdf_files:
            pdf_file_paths = [Path(f) for f in pdf_files]
        else:
            # Find all PDFs (recursively)
            pdf_file_paths = list(pdf_dir.rglob("*.pdf"))
        
        if limit:
            pdf_file_paths = pdf_file_paths[:limit]
        
        logger.info(f"Processing {len(pdf_file_paths)} PDF files from {pdf_dir}")
        
        # Build list of (pdf_path, metadata_row) tuples
        tasks: List[Tuple[Path, Optional[Dict]]] = []
        for pdf_path in pdf_file_paths:
            metadata_row = None
            if metadata_map:
                for case_num, row in metadata_map.items():
                    if case_num in pdf_path.name or row.get('pdf_filename', '') == pdf_path.name:
                        metadata_row = row
                        break
            tasks.append((pdf_path, metadata_row))
        
        if parallel and len(tasks) > 1:
            return self._process_batch_parallel(tasks)
        else:
            return self._process_batch_sequential(tasks)
    
    def _process_batch_sequential(self, tasks: List[Tuple[Path, Optional[Dict]]]) -> List[ExtractedCase]:
        """Process tasks sequentially."""
        results = []
        total = len(tasks)
        
        for i, (pdf_path, metadata_row) in enumerate(tasks, 1):
            logger.info(f"\n[{i}/{total}] Processing: {pdf_path.name}")
            case = self.process_case(str(pdf_path), metadata_row)
            results.append(case)
            
            if case.extraction_successful:
                logger.info(f"  [OK] Success")
            else:
                logger.warning(f"  [FAIL] {case.error_message}")
        
        successful = sum(1 for c in results if c.extraction_successful)
        logger.info(f"\nBatch complete: {successful}/{len(results)} successful")
        return results
    
    def _process_batch_parallel(self, tasks: List[Tuple[Path, Optional[Dict]]]) -> List[ExtractedCase]:
        """Process tasks in parallel using ThreadPoolExecutor."""
        results = []
        total = len(tasks)
        counter = {'completed': 0}  # Use dict for mutable counter
        lock = threading.Lock()
        
        logger.info(f"Using {self.max_workers} parallel workers")
        
        def process_task(task_info: Tuple[int, Path, Optional[Dict]]) -> Tuple[int, ExtractedCase]:
            """Worker function to process a single case."""
            idx, pdf_path, metadata_row = task_info
            case = self.process_case(str(pdf_path), metadata_row)
            return (idx, case)
        
        # Create indexed tasks
        indexed_tasks = [(i, pdf_path, metadata_row) for i, (pdf_path, metadata_row) in enumerate(tasks)]
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {executor.submit(process_task, task): task for task in indexed_tasks}
            
            # Collect results as they complete
            for future in as_completed(futures):
                task = futures[future]
                idx, pdf_path, _ = task
                
                try:
                    result_idx, case = future.result()
                    results.append((result_idx, case))
                    
                    with lock:
                        counter['completed'] += 1
                        status = "[OK]" if case.extraction_successful else "[FAIL]"
                        logger.info(f"[{counter['completed']}/{total}] {status} {pdf_path.name}")
                        
                except Exception as e:
                    with lock:
                        counter['completed'] += 1
                        logger.error(f"[{counter['completed']}/{total}] [ERROR] {pdf_path.name}: {e}")
                    
                    # Create failed case
                    case = ExtractedCase()
                    case.extraction_successful = False
                    case.error_message = str(e)
                    results.append((idx, case))
        
        # Sort by original order and extract cases
        results.sort(key=lambda x: x[0])
        ordered_cases = [case for _, case in results]
        
        successful = sum(1 for c in ordered_cases if c.extraction_successful)
        logger.info(f"\nBatch complete: {successful}/{len(ordered_cases)} successful")
        
        return ordered_cases
