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
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> Tuple[str, int]:
        """
        Extract text using pdfplumber (local, faster but less accurate).
        
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
            
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages_text.append(text)
            
            full_text = "\n\n".join(pages_text)
            logger.info(f"pdfplumber extracted {len(full_text)} chars from {page_count} pages")
            
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
