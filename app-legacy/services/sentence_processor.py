"""
Sentence Processing Service
Handles splitting chunks into sentences and creating sentence-level embeddings.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.engine import Engine
# from .embedding_service import generate_embedding  # Not needed - no sentence embeddings

logger = logging.getLogger(__name__)

class SentenceProcessor:
    """Service for processing text chunks into sentences"""
    
    def __init__(self, db_engine: Engine):
        self.db = db_engine
    
    def split_chunk_into_sentences(self, chunk_text: str) -> List[Dict[str, Any]]:
        """
        Split chunk text into individual sentences
        
        Args:
            chunk_text: Text content to split
            
        Returns:
            List of sentence dictionaries with text and metadata
        """
        # Enhanced sentence splitting for legal text
        # Legal documents often have complex punctuation and citations
        
        # First, protect citations and case references
        protected_patterns = [
            r'\d+\s+P\.\s*\d+d?\s+\d+',  # Pacific Reporter citations
            r'\d+\s+Wn\.\s*\d*\s+\d+',   # Washington Reports
            r'\d+\s+U\.S\.\s+\d+',       # U.S. Reports
            r'RCW\s+\d+\.\d+\.\d+',      # RCW statutes
            r'WAC\s+\d+\-\d+\-\d+',     # WAC regulations
        ]
        
        text = chunk_text
        protections = {}
        
        # Protect citations from splitting
        for i, pattern in enumerate(protected_patterns):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                placeholder = f"__CITATION_{i}_{len(protections)}__"
                protections[placeholder] = match.group()
                text = text.replace(match.group(), placeholder)
        
        # Split on sentence boundaries
        # Look for periods, question marks, exclamation points followed by space and capital letter
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        raw_sentences = re.split(sentence_pattern, text)
        
        sentences = []
        for i, sent in enumerate(raw_sentences):
            sent = sent.strip()
            if not sent:
                continue
            
            # Restore protected citations
            for placeholder, original in protections.items():
                sent = sent.replace(placeholder, original)
            
            # Skip very short sentences (likely fragments)
            if len(sent) < 10:
                continue
            
            # Count words
            word_count = len(sent.split())
            
            sentences.append({
                'text': sent,
                'sentence_order': i + 1,
                'word_count': word_count,
                'length': len(sent)
            })
        
        return sentences
    
    def process_chunk_sentences(self, case_id: int, chunk_id: int, chunk_text: str, 
                               document_id: Optional[int] = None, 
                               global_sentence_counter: int = 0) -> List[Dict[str, Any]]:
        """
        Process chunk into sentences and create database records
        
        Args:
            case_id: Case ID
            chunk_id: Chunk ID  
            chunk_text: Text content
            document_id: Optional document ID
            global_sentence_counter: Starting counter for global sentence order
            
        Returns:
            List of created sentence records with IDs
        """
        try:
            # Split into sentences
            sentences = self.split_chunk_into_sentences(chunk_text)
            
            if not sentences:
                logger.warning(f"No sentences found in chunk {chunk_id}")
                return []
            
            logger.info(f"Split chunk {chunk_id} into {len(sentences)} sentences")
            
            # Create sentence records
            sentence_records = []
            
            with self.db.connect() as conn:
                for sentence_data in sentences:
                    # Skip sentence embeddings - too expensive and not needed!
                    embedding_list = None
                    
                    # Insert sentence record
                    insert_query = text("""
                        INSERT INTO case_sentences (
                            case_id, chunk_id, document_id, sentence_order, 
                            global_sentence_order, text, word_count,
                            created_at, updated_at
                        ) VALUES (
                            :case_id, :chunk_id, :document_id, :sentence_order,
                            :global_sentence_order, :text, :word_count,
                            NOW(), NOW()
                        )
                        RETURNING sentence_id
                    """)
                    
                    global_sentence_counter += 1
                    
                    try:
                        result = conn.execute(insert_query, {
                            'case_id': case_id,
                            'chunk_id': chunk_id,
                            'document_id': document_id,
                            'sentence_order': sentence_data['sentence_order'],
                            'global_sentence_order': global_sentence_counter,
                            'text': sentence_data['text'],
                            'word_count': sentence_data['word_count']
                        })
                        
                        sentence_id = result.fetchone().sentence_id
                        
                        # Add to results
                        sentence_record = {
                            'sentence_id': sentence_id,
                            'case_id': case_id,
                            'chunk_id': chunk_id,
                            'document_id': document_id,
                            'sentence_order': sentence_data['sentence_order'],
                            'global_sentence_order': global_sentence_counter,
                            'text': sentence_data['text'],
                            'word_count': sentence_data['word_count'],
                            'embedding': embedding_list
                        }
                        sentence_records.append(sentence_record)
                        
                    except Exception as e:
                        logger.error(f"Failed to insert sentence: {e}")
                        continue
                
                # Commit all sentences
                conn.commit()
                
            logger.info(f"Created {len(sentence_records)} sentence records for chunk {chunk_id}")
            return sentence_records
            
        except Exception as e:
            logger.error(f"Error processing sentences for chunk {chunk_id}: {e}")
            return []
    
    def update_chunk_sentence_count(self, chunk_id: int, sentence_count: int) -> None:
        """Update the sentence count for a chunk"""
        try:
            with self.db.connect() as conn:
                query = text("UPDATE case_chunks SET sentence_count = :count WHERE chunk_id = :chunk_id")
                conn.execute(query, {'count': sentence_count, 'chunk_id': chunk_id})
                conn.commit()
                logger.debug(f"Updated chunk {chunk_id} sentence count to {sentence_count}")
        except Exception as e:
            logger.error(f"Failed to update chunk sentence count: {e}")
    
    def get_case_sentence_stats(self, case_id: int) -> Dict[str, Any]:
        """Get sentence statistics for a case"""
        try:
            with self.db.connect() as conn:
                query = text("""
                    SELECT 
                        COUNT(*) as total_sentences,
                        AVG(word_count) as avg_words_per_sentence,
                        MIN(word_count) as min_words,
                        MAX(word_count) as max_words,
                        SUM(word_count) as total_words
                    FROM case_sentences 
                    WHERE case_id = :case_id
                """)
                
                result = conn.execute(query, {'case_id': case_id})
                row = result.fetchone()
                
                if row:
                    return {
                        'total_sentences': row.total_sentences or 0,
                        'avg_words_per_sentence': float(row.avg_words_per_sentence or 0),
                        'min_words': row.min_words or 0,
                        'max_words': row.max_words or 0,
                        'total_words': row.total_words or 0
                    }
                else:
                    return {
                        'total_sentences': 0,
                        'avg_words_per_sentence': 0.0,
                        'min_words': 0,
                        'max_words': 0,
                        'total_words': 0
                    }
                    
        except Exception as e:
            logger.error(f"Error getting sentence stats for case {case_id}: {e}")
            return {
                'total_sentences': 0,
                'avg_words_per_sentence': 0.0,
                'min_words': 0,
                'max_words': 0,
                'total_words': 0
            }
