"""
PDF Text Extraction using LlamaParse
Production-grade PDF OCR and text extraction for legal documents.
"""

import os
import logging
import time
import threading
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent LlamaParse API calls
_llamaparse_semaphore = threading.Semaphore(2)  # Max 2 concurrent calls


class PDFExtractor:
    """
    Extract text from PDF files using LlamaParse or pdfplumber.
    """
    
    def __init__(self, llama_cloud_api_key: Optional[str] = None, mode: str = "llamaparse"):
        """
        Initialize the PDF extractor.
        
        Args:
            llama_cloud_api_key: API key for LlamaParse. 
                                 If not provided, reads from LLAMA_CLOUD_API_KEY env var.
            mode: Extraction mode - 'llamaparse', 'pdfplumber', or 'auto' (try llamaparse, fallback to pdfplumber)
        """
        self.api_key = llama_cloud_api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        self._llama_parser = None
        self._llamaparse_available = False
        self.mode = mode.lower()
        
        # Try to initialize LlamaParse if needed
        if self.mode in ("llamaparse", "auto") and self.api_key:
            try:
                from llama_parse import LlamaParse
                self._llama_parser = LlamaParse(
                    api_key=self.api_key,
                    result_type="text",
                    num_workers=1,  # Reduced for stability
                    verbose=False,
                    language="en",
                )
                self._llamaparse_available = True
                logger.info("LlamaParse initialized successfully")
            except ImportError:
                logger.warning("llama-parse not installed. Run: pip install llama-parse")
            except Exception as e:
                logger.warning(f"Failed to initialize LlamaParse: {e}")
        
        # Log the mode being used
        if self.mode == "pdfplumber":
            logger.info("Using pdfplumber for PDF extraction")
        elif self.mode == "llamaparse" and not self._llamaparse_available:
            logger.warning("LlamaParse requested but not available, will use pdfplumber")
        elif self.mode == "auto":
            logger.info(f"Auto mode: LlamaParse {'available' if self._llamaparse_available else 'unavailable, using pdfplumber'}")
    
    def _should_use_llamaparse(self) -> bool:
        """Determine if LlamaParse should be used based on mode and availability."""
        if self.mode == "pdfplumber":
            return False
        if self.mode == "llamaparse":
            return self._llamaparse_available
        if self.mode == "auto":
            return self._llamaparse_available
        return False
    
    def extract_text(self, pdf_path: str) -> Tuple[str, int]:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (extracted_text, page_count)
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if self._should_use_llamaparse():
            return self._extract_with_llamaparse(pdf_path)
        else:
            return self._extract_with_pdfplumber(pdf_path)
    
    def extract_text_from_bytes(self, pdf_content: bytes, filename: str = "document.pdf") -> Tuple[str, int]:
        """
        Extract text from PDF bytes.
        
        Args:
            pdf_content: PDF file content as bytes
            filename: Filename hint for LlamaParse
            
        Returns:
            Tuple of (extracted_text, page_count)
        """
        import tempfile
        
        # Write to temp file for processing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_content)
            tmp_path = tmp.name
        
        try:
            return self.extract_text(tmp_path)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _extract_with_llamaparse(self, pdf_path: Path) -> Tuple[str, int]:
        """
        Extract text using LlamaParse (cloud-based, high quality).
        Uses semaphore to limit concurrent API calls and retries on failure.
        Automatically removes slip opinion notice text if present.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, page_count)
        """
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Limit concurrent LlamaParse calls
                with _llamaparse_semaphore:
                    logger.info(f"Extracting with LlamaParse: {pdf_path.name}")
                    
                    # LlamaParse returns a list of Document objects
                    documents = self._llama_parser.load_data(str(pdf_path))
                    
                    # Combine all document text
                    full_text = "\n\n".join([doc.text for doc in documents])
                    
                    # Remove slip opinion notice if present at the beginning
                    full_text = self._remove_slip_opinion_notice(full_text)
                    
                    # Estimate page count
                    page_count = self._get_page_count(pdf_path)
                    
                    # Check if we got meaningful content
                    if len(full_text.strip()) < 100:
                        logger.warning(f"LlamaParse returned only {len(full_text)} chars, retrying...")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        else:
                            # Final attempt failed, fall back to pdfplumber
                            logger.warning(f"LlamaParse failed after {max_retries} attempts, using pdfplumber")
                            return self._extract_with_pdfplumber(pdf_path)
                    
                    logger.info(f"LlamaParse extracted {len(full_text)} chars from {page_count} pages")
                    return full_text, page_count
                
            except Exception as e:
                logger.warning(f"LlamaParse attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.warning(f"LlamaParse failed after {max_retries} attempts, falling back to pdfplumber")
                    return self._extract_with_pdfplumber(pdf_path)
        
        # Should not reach here, but fallback just in case
        return self._extract_with_pdfplumber(pdf_path)
    
    def _remove_slip_opinion_notice(self, text: str) -> str:
        """
        Remove the slip opinion notice from the beginning of extracted text.
        This handles cases where LlamaParse combines all pages into one text block.
        
        Args:
            text: Full extracted text
            
        Returns:
            Text with slip opinion notice removed
        """
        import re
        
        # Pattern to match the slip opinion notice section
        # It starts with "NOTICE: SLIP OPINION" and ends around the courts.wa.gov link
        slip_notice_pattern = re.compile(
            r'^.*?NOTICE:\s*SLIP\s*OPINION.*?(?:courts\.wa\.gov/opinions|linked there\.)\s*',
            re.DOTALL | re.IGNORECASE
        )
        
        # Check if text starts with slip opinion notice
        if 'NOTICE' in text[:500] and 'SLIP OPINION' in text[:500]:
            cleaned = slip_notice_pattern.sub('', text, count=1)
            if cleaned != text:
                logger.info("Removed slip opinion notice from text")
            return cleaned.strip()
        
        return text
    
    def _is_slip_opinion_notice_page(self, page_text: str) -> bool:
        """
        Check if a page is the standard Washington State slip opinion notice page.
        
        Args:
            page_text: Text content of the page
            
        Returns:
            True if this is a slip opinion notice page that should be skipped
        """
        if not page_text:
            return False
        
        # Key phrases that identify the slip opinion notice page
        slip_opinion_markers = [
            "NOTICE: SLIP OPINION",
            "not the court's final written decision",
            "slip opinion that begins on the next page",
            "Slip opinions are the written opinions that are originally filed"
        ]
        
        # Check if multiple markers are present (to avoid false positives)
        markers_found = sum(1 for marker in slip_opinion_markers if marker.lower() in page_text.lower())
        
        # If at least 2 markers found and page is relatively short (notice pages are typically <2000 chars)
        return markers_found >= 2 and len(page_text) < 3000
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> Tuple[str, int]:
        """
        Extract text using pdfplumber (local, faster but less accurate).
        Automatically skips the slip opinion notice page if present.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, page_count)
        """
        try:
            import pdfplumber
            
            logger.info(f"Extracting with pdfplumber: {pdf_path.name}")
            
            pages_text = []
            page_count = 0
            skipped_slip_notice = False
            
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    
                    # Check if first page is a slip opinion notice - skip it
                    if i == 0 and self._is_slip_opinion_notice_page(text):
                        logger.info(f"Skipping slip opinion notice page (page 1)")
                        skipped_slip_notice = True
                        continue
                    
                    pages_text.append(text)
            
            full_text = "\n\n".join(pages_text)
            actual_pages = page_count - (1 if skipped_slip_notice else 0)
            logger.info(f"pdfplumber extracted {len(full_text)} chars from {actual_pages} pages" + 
                       (" (skipped slip notice)" if skipped_slip_notice else ""))
            
            return full_text, page_count
            
        except ImportError:
            raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
    
    def _get_page_count(self, pdf_path: Path) -> int:
        """Get page count using pdfplumber (lightweight operation)."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except:
            return 0
    
    @property
    def using_llamaparse(self) -> bool:
        """Check if LlamaParse is being used."""
        return self._use_llamaparse
