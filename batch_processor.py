#!/usr/bin/env python3
"""
Legal Case Batch PDF Processor
Complete batch processing with AI extraction and comprehensive RAG capabilities.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
import argparse
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import engine
from app.services.case_ingestor import LegalCaseIngestor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_processing.log')
    ]
)

logger = logging.getLogger(__name__)

class BatchProcessor:
    """Legal case batch processor"""
    
    def __init__(self):
        self.engine = engine
        self.ingestor = LegalCaseIngestor(self.engine)
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = None
    
    def process_pdf_file(self, pdf_path: Path) -> bool:
        """
        Process a single PDF file
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if successful, False if failed
        """
        try:
            logger.info(f"📄 Processing: {pdf_path.name}")
            
            # Read PDF content
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # Prepare metadata
            metadata = {
                'case_number': pdf_path.stem,  # Use filename as case number
                'title': pdf_path.stem.replace('_', ' ').title(),
                'court_level': 'Appeals',  # Default for family law
                'division': 'Unknown',
                'publication': 'Unknown'
            }
            
            # Prepare source file info
            source_file_info = {
                'filename': pdf_path.name,
                'file_path': str(pdf_path.absolute())
            }
            
            # Process with case ingestor
            result = self.ingestor.ingest_pdf_case(
                pdf_content=pdf_content,
                metadata=metadata,
                source_file_info=source_file_info,
                enable_ai_extraction=True
            )
            
            # Log results
            logger.info(f"✅ Successfully processed {pdf_path.name}")
            logger.info(f"   Case ID: {result['case_id']}")
            logger.info(f"   AI Extraction: {'✓' if result['ai_extraction'] else '✗'}")
            logger.info(f"   Chunks: {result['chunks_created']}")
            logger.info(f"   Words: {result['words_processed']} ({result['unique_words']} unique)")
            logger.info(f"   Phrases: {result['phrases_extracted']}")
            logger.info(f"   Entities: {sum(result['case_stats'].values())}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to process {pdf_path.name}: {str(e)}")
            return False
    
    def process_directory(self, pdf_dir: Path, limit: Optional[int] = None) -> None:
        """
        Process all PDF files in a directory
        
        Args:
            pdf_dir: Directory containing PDF files
            limit: Optional limit on number of files to process
        """
        # Find all PDF files
        pdf_files = list(pdf_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.error(f"No PDF files found in {pdf_dir}")
            return
        
        if limit:
            pdf_files = pdf_files[:limit]
        
        logger.info(f"🚀 Starting legal case batch processing")
        logger.info(f"📁 Source Directory: {pdf_dir}")
        logger.info(f"📄 Files to process: {len(pdf_files)}")
        logger.info(f"🤖 AI Extraction: Enabled (Ollama + OpenAI fallback)")
        logger.info(f"🔍 RAG Features: Full (chunks + words + phrases + embeddings)")
        
        self.start_time = datetime.now()
        
        # Process files
        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📄 Processing PDF {i}/{len(pdf_files)}: {pdf_path.name}")
            logger.info(f"{'='*60}")
            
            success = self.process_pdf_file(pdf_path)
            
            if success:
                self.processed_count += 1
            else:
                self.failed_count += 1
            
            # Progress update
            elapsed = datetime.now() - self.start_time
            rate = i / elapsed.total_seconds() * 60 if elapsed.total_seconds() > 0 else 0
            
            logger.info(f"📊 Progress: {i}/{len(pdf_files)} files processed")
            logger.info(f"✅ Success: {self.processed_count}, ❌ Failed: {self.failed_count}")
            logger.info(f"⏱️ Rate: {rate:.1f} files/minute")
        
        # Final summary
        self._print_final_summary(len(pdf_files))
    
    def _print_final_summary(self, total_files: int) -> None:
        """Print final processing summary"""
        elapsed = datetime.now() - self.start_time
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 LEGAL CASE BATCH PROCESSING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"📊 Total Files: {total_files}")
        logger.info(f"✅ Successfully Processed: {self.processed_count}")
        logger.info(f"❌ Failed: {self.failed_count}")
        logger.info(f"📈 Success Rate: {(self.processed_count/total_files*100):.1f}%")
        logger.info(f"⏱️ Total Time: {elapsed}")
        logger.info(f"⚡ Average Rate: {self.processed_count/elapsed.total_seconds()*60:.1f} files/minute")
        logger.info(f"💾 Log File: batch_processing.log")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Legal Case PDF Batch Processor')
    parser.add_argument('pdf_directory', help='Directory containing PDF files')
    parser.add_argument('--limit', type=int, help='Limit number of files to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate directory
    pdf_dir = Path(args.pdf_directory)
    if not pdf_dir.exists():
        logger.error(f"Directory does not exist: {pdf_dir}")
        sys.exit(1)
    
    if not pdf_dir.is_dir():
        logger.error(f"Path is not a directory: {pdf_dir}")
        sys.exit(1)
    
    # Create processor and run
    processor = BatchProcessor()
    processor.process_directory(pdf_dir, args.limit)

if __name__ == "__main__":
    main()
