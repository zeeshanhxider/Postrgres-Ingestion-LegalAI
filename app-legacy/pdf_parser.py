import PyPDF2
import re
import logging
from typing import List, Dict
from io import BytesIO

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_content: bytes) -> List[str]:
    """
    Extract text from PDF content, returning a list of page texts.
    
    Args:
        pdf_content: PDF file content as bytes
        
    Returns:
        List of strings, one per page
    """
    try:
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        pages = []
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                text = page.extract_text()
                cleaned_text = clean_pdf_text(text)
                if cleaned_text.strip():  # Only add non-empty pages
                    pages.append(cleaned_text)
                    logger.info(f"Extracted page {page_num + 1}: {len(cleaned_text)} characters")
                else:
                    logger.warning(f"Page {page_num + 1} is empty after cleaning")
            except Exception as e:
                logger.error(f"Error extracting page {page_num + 1}: {str(e)}")
                continue
        
        logger.info(f"Successfully extracted {len(pages)} pages from PDF")
        return pages
        
    except Exception as e:
        logger.error(f"Error reading PDF: {str(e)}")
        raise ValueError(f"Failed to parse PDF: {str(e)}")


def clean_pdf_text(text: str) -> str:
    """
    Clean and normalize text extracted from PDF.
    
    Args:
        text: Raw text from PDF
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace and normalize line breaks
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Remove header/footer patterns (common in legal docs)
    text = remove_headers_footers(text)
    
    # Fix common PDF extraction issues
    text = fix_pdf_artifacts(text)
    
    # Normalize quotes and dashes
    text = normalize_punctuation(text)
    
    return text.strip()


def remove_headers_footers(text: str) -> str:
    """Remove common header/footer patterns from legal documents"""
    
    # Remove page numbers at start/end of lines
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    
    # Remove common legal document headers
    header_patterns = [
        r'^\s*IN THE .* COURT.*$',
        r'^\s*STATE OF .*$',
        r'^\s*COUNTY OF .*$',
        r'^\s*No\.\s*\d+.*$',
        r'^\s*Case No\..*$',
        r'^\s*Docket.*$'
    ]
    
    for pattern in header_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    return text


def fix_pdf_artifacts(text: str) -> str:
    """Fix common PDF text extraction artifacts"""
    
    # Fix broken words (common in PDFs)
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    
    # Fix spacing around punctuation
    text = re.sub(r'\s+([,.;:!?])', r'\1', text)
    text = re.sub(r'([,.;:!?])\s*([A-Z])', r'\1 \2', text)
    
    # Fix parentheses spacing
    text = re.sub(r'\s*\(\s*', ' (', text)
    text = re.sub(r'\s*\)\s*', ') ', text)
    
    # Remove zero-width characters and other Unicode artifacts
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)
    
    return text


def normalize_punctuation(text: str) -> str:
    """Normalize quotation marks and dashes"""
    
    # Normalize quotes
    text = re.sub(r'["""]', '"', text)
    text = re.sub(r"[''']", "'", text)
    
    # Normalize dashes
    text = re.sub(r'[–—]', '-', text)
    
    return text


def get_pdf_metadata(pdf_content: bytes) -> Dict[str, str]:
    """
    Extract metadata from PDF if available.
    
    Args:
        pdf_content: PDF file content as bytes
        
    Returns:
        Dictionary of metadata
    """
    try:
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        metadata = {}
        if pdf_reader.metadata:
            for key, value in pdf_reader.metadata.items():
                if value:
                    clean_key = key.replace('/', '').lower()
                    metadata[clean_key] = str(value)
        
        # Add page count
        metadata['page_count'] = len(pdf_reader.pages)
        
        return metadata
        
    except Exception as e:
        logger.warning(f"Could not extract PDF metadata: {str(e)}")
        return {}


def validate_pdf_content(pdf_content: bytes) -> bool:
    """
    Validate that the content is a valid PDF.
    
    Args:
        pdf_content: PDF file content as bytes
        
    Returns:
        True if valid PDF, False otherwise
    """
    try:
        pdf_file = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Try to access basic properties
        _ = len(pdf_reader.pages)
        
        # Check if we can extract at least some text
        if len(pdf_reader.pages) > 0:
            first_page_text = pdf_reader.pages[0].extract_text()
            if not first_page_text.strip():
                logger.warning("PDF appears to contain no extractable text")
        
        return True
        
    except Exception as e:
        logger.error(f"PDF validation failed: {str(e)}")
        return False