import re
import logging
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata"""
    order: int
    text: str
    word_count: int
    char_count: int
    section: str = "CONTENT"


class LegalTextChunker:
    """
    Chunks legal text into semantically meaningful pieces.
    
    Designed for legal documents with typical patterns:
    - Court headers
    - Procedural sections
    - Facts sections
    - Analysis/Discussion
    - Conclusions
    """
    
    def __init__(
        self, 
        target_chunk_size: int = 350,  # Target words per chunk
        min_chunk_size: int = 200,     # Minimum words per chunk
        max_chunk_size: int = 500      # Maximum words per chunk
    ):
        self.target_chunk_size = target_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
        # Legal document section patterns
        self.section_patterns = {
            "HEADER": [
                r"IN THE .* COURT",
                r"STATE OF .*",
                r"COUNTY OF .*",
                r"No\.\s*\d+",
                r"Case No\.",
                r"Docket"
            ],
            "PARTIES": [
                r"Plaintiff",
                r"Defendant", 
                r"Appellant",
                r"Respondent",
                r"Petitioner"
            ],
            "PROCEDURAL": [
                r"PROCEDURAL HISTORY",
                r"BACKGROUND",
                r"PROCEEDINGS",
                r"MOTION",
                r"APPEAL"
            ],
            "FACTS": [
                r"STATEMENT OF FACTS",
                r"FACTUAL BACKGROUND", 
                r"FACTS",
                r"FINDINGS OF FACT"
            ],
            "ANALYSIS": [
                r"ANALYSIS",
                r"DISCUSSION", 
                r"LEGAL ANALYSIS",
                r"CONCLUSIONS OF LAW",
                r"OPINION"
            ],
            "HOLDING": [
                r"HOLDING",
                r"CONCLUSION",
                r"DECISION",
                r"JUDGMENT",
                r"ORDER"
            ]
        }
    
    def chunk_pages(self, pages: List[str]) -> List[TextChunk]:
        """
        Chunk a list of page texts into semantic chunks.
        
        Args:
            pages: List of page texts from PDF
            
        Returns:
            List of TextChunk objects in order
        """
        # Combine all pages into single text
        full_text = "\n\n".join(pages)
        
        # Split into paragraphs first
        paragraphs = self._split_into_paragraphs(full_text)
        
        # Identify sections
        sectioned_paragraphs = self._identify_sections(paragraphs)
        
        # Create chunks respecting section boundaries
        chunks = self._create_chunks(sectioned_paragraphs)
        
        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split on double line breaks or more
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Clean and filter empty paragraphs
        cleaned_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and len(para.split()) >= 5:  # At least 5 words
                cleaned_paragraphs.append(para)
        
        return cleaned_paragraphs
    
    def _identify_sections(self, paragraphs: List[str]) -> List[Dict[str, str]]:
        """Identify which section each paragraph belongs to"""
        sectioned = []
        current_section = "CONTENT"
        
        for para in paragraphs:
            # Check if this paragraph is a section header
            detected_section = self._detect_section(para)
            if detected_section:
                current_section = detected_section
            
            sectioned.append({
                "text": para,
                "section": current_section
            })
        
        return sectioned
    
    def _detect_section(self, paragraph: str) -> str:
        """Detect if paragraph is a section header"""
        para_upper = paragraph.upper()
        
        for section_name, patterns in self.section_patterns.items():
            for pattern in patterns:
                if re.search(pattern, para_upper):
                    return section_name
        
        return None
    
    def _create_chunks(self, sectioned_paragraphs: List[Dict[str, str]]) -> List[TextChunk]:
        """Create chunks from sectioned paragraphs"""
        chunks = []
        current_chunk_paras = []
        current_section = "CONTENT"
        chunk_order = 1
        
        for para_data in sectioned_paragraphs:
            para_text = para_data["text"]
            para_section = para_data["section"]
            
            # If section changes and we have content, finalize current chunk
            if para_section != current_section and current_chunk_paras:
                chunk = self._finalize_chunk(current_chunk_paras, chunk_order, current_section)
                if chunk:
                    chunks.append(chunk)
                    chunk_order += 1
                current_chunk_paras = []
            
            current_section = para_section
            current_chunk_paras.append(para_text)
            
            # Check if current chunk is large enough
            current_word_count = sum(len(p.split()) for p in current_chunk_paras)
            
            if current_word_count >= self.target_chunk_size:
                # If we're over max size, split the chunk
                if current_word_count > self.max_chunk_size:
                    # Split into multiple chunks
                    sub_chunks = self._split_large_chunk(current_chunk_paras, chunk_order, current_section)
                    chunks.extend(sub_chunks)
                    chunk_order += len(sub_chunks)
                else:
                    # Finalize at target size
                    chunk = self._finalize_chunk(current_chunk_paras, chunk_order, current_section)
                    if chunk:
                        chunks.append(chunk)
                        chunk_order += 1
                
                current_chunk_paras = []
        
        # Handle remaining paragraphs
        if current_chunk_paras:
            chunk = self._finalize_chunk(current_chunk_paras, chunk_order, current_section)
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def _finalize_chunk(self, paragraphs: List[str], order: int, section: str) -> TextChunk:
        """Create a TextChunk from paragraphs"""
        if not paragraphs:
            return None
        
        text = "\n\n".join(paragraphs)
        word_count = len(text.split())
        
        # Skip chunks that are too small
        if word_count < self.min_chunk_size:
            logger.debug(f"Skipping chunk {order}: too small ({word_count} words)")
            return None
        
        return TextChunk(
            order=order,
            text=text,
            word_count=word_count,
            char_count=len(text),
            section=section
        )
    
    def _split_large_chunk(self, paragraphs: List[str], start_order: int, section: str) -> List[TextChunk]:
        """Split large chunks into smaller ones"""
        chunks = []
        current_paras = []
        current_order = start_order
        
        for para in paragraphs:
            current_paras.append(para)
            current_word_count = sum(len(p.split()) for p in current_paras)
            
            if current_word_count >= self.target_chunk_size:
                chunk = self._finalize_chunk(current_paras, current_order, section)
                if chunk:
                    chunks.append(chunk)
                    current_order += 1
                current_paras = []
        
        # Handle remaining paragraphs
        if current_paras:
            # If too small, merge with last chunk if possible
            if len(current_paras) == 1 and chunks:
                last_chunk = chunks[-1]
                merged_text = last_chunk.text + "\n\n" + current_paras[0]
                merged_word_count = len(merged_text.split())
                
                if merged_word_count <= self.max_chunk_size:
                    # Merge with last chunk
                    chunks[-1] = TextChunk(
                        order=last_chunk.order,
                        text=merged_text,
                        word_count=merged_word_count,
                        char_count=len(merged_text),
                        section=section
                    )
                else:
                    # Create separate chunk
                    chunk = self._finalize_chunk(current_paras, current_order, section)
                    if chunk:
                        chunks.append(chunk)
            else:
                chunk = self._finalize_chunk(current_paras, current_order, section)
                if chunk:
                    chunks.append(chunk)
        
        return chunks


def chunk_case_text(pages: List[str], **kwargs) -> List[TextChunk]:
    """
    Convenience function to chunk case text.
    
    Args:
        pages: List of page texts
        **kwargs: Additional arguments for LegalTextChunker
        
    Returns:
        List of TextChunk objects
    """
    chunker = LegalTextChunker(**kwargs)
    return chunker.chunk_pages(pages)