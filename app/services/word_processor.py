"""
Word processing for word dictionary and occurrence tracking
This enables precise phrase queries and word-level indexing for RAG
"""

import re
import logging
from typing import List, Dict, Tuple, Set, Optional
from collections import Counter
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

class WordProcessor:
    """Process text for word dictionary and occurrence tracking"""
    
    def __init__(self, db_engine: Engine):
        self.db = db_engine
        
    def tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize text into words, preserving legal terminology
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of normalized word tokens
        """
        if not text:
            return []
            
        # Normalize text
        text = text.lower()
        
        # Split on whitespace and punctuation, but preserve legal terms
        # Keep hyphens in compound words, apostrophes in contractions
        tokens = re.findall(r"\b[\w'-]+\b", text)
        
        # Filter out very short tokens and numbers-only tokens
        filtered_tokens = []
        for token in tokens:
            # Keep if it's at least 2 characters and contains at least one letter
            if len(token) >= 2 and re.search(r'[a-zA-Z]', token):
                # Remove apostrophes at the end (possessives)
                token = re.sub(r"'s?$", "", token)
                if token:  # Make sure it's not empty after cleaning
                    filtered_tokens.append(token)
        
        return filtered_tokens
    
    def get_or_create_word_ids(self, words: List[str]) -> Dict[str, int]:
        """
        Get or create word IDs for a list of words
        
        Args:
            words: List of unique words
            
        Returns:
            Dictionary mapping word -> word_id
        """
        if not words:
            return {}
            
        word_to_id = {}
        
        with self.db.connect() as conn:
            # First, try to get existing words
            if words:
                placeholders = ','.join([':word_' + str(i) for i in range(len(words))])
                query = text(f"""
                    SELECT word_id, word 
                    FROM word_dictionary 
                    WHERE word = ANY(ARRAY[{placeholders}])
                """)
                
                params = {f'word_{i}': word for i, word in enumerate(words)}
                result = conn.execute(query, params)
                
                for row in result:
                    word_to_id[row.word] = row.word_id
            
            # Create new words that don't exist
            new_words = [word for word in words if word not in word_to_id]
            
            if new_words:
                # Insert new words
                insert_query = text("""
                    INSERT INTO word_dictionary (word) 
                    VALUES (:word)
                    ON CONFLICT (word) DO UPDATE SET word = EXCLUDED.word
                    RETURNING word_id, word
                """)
                
                for word in new_words:
                    result = conn.execute(insert_query, {'word': word})
                    row = result.fetchone()
                    word_to_id[word] = row.word_id
            
            conn.commit()
        
        return word_to_id
    
    def process_sentence_words(self, case_id: int, chunk_id: int, sentence_id: int, 
                              sentence_text: str, document_id: Optional[int] = None) -> Dict[str, any]:
        """
        Process a sentence's text for word occurrences
        
        Args:
            case_id: Case identifier
            chunk_id: Chunk identifier
            sentence_id: Sentence identifier  
            sentence_text: Sentence text content
            document_id: Document identifier
            
        Returns:
            Dictionary with processing stats
        """
        if not sentence_text:
            return {'words_processed': 0, 'unique_words': 0}
            
        # Tokenize the sentence text
        tokens = self.tokenize_text(sentence_text)
        
        if not tokens:
            return {'words_processed': 0, 'unique_words': 0}
        
        # Get unique words
        unique_words = list(set(tokens))
        
        # Get or create word IDs
        word_to_id = self.get_or_create_word_ids(unique_words)
        
        # Create word occurrences (positions are relative to sentence, not chunk)
        word_occurrences = []
        for position, word in enumerate(tokens):
            if word in word_to_id:
                word_occurrences.append({
                    'word_id': word_to_id[word],
                    'case_id': case_id,
                    'chunk_id': chunk_id,
                    'sentence_id': sentence_id,
                    'document_id': document_id,
                    'position': position  # Position within sentence (0-based)
                })
        
        # Insert word occurrences in batches
        if word_occurrences:
            self._insert_word_occurrences(word_occurrences)
        
        logger.debug(f"Processed {len(tokens)} words, {len(unique_words)} unique for sentence {sentence_id}")
        
        return {
            'words_processed': len(tokens),
            'unique_words': len(unique_words),
            'word_occurrences': len(word_occurrences)
        }
    
    def process_case_sentences_words(self, case_id: int, document_id: Optional[int] = None) -> Dict[str, int]:
        """
        Process words for all sentences in a case by querying existing sentence records
        
        Args:
            case_id: Case identifier
            document_id: Optional document identifier
            
        Returns:
            Dictionary with processing stats
        """
        total_words = 0
        unique_words = set()
        
        try:
            with self.db.connect() as conn:
                # Get all sentences for this case
                query = text("""
                    SELECT sentence_id, chunk_id, text 
                    FROM case_sentences 
                    WHERE case_id = :case_id
                    ORDER BY chunk_id, sentence_order
                """)
                
                result = conn.execute(query, {'case_id': case_id})
                sentences = result.fetchall()
                
                logger.info(f"Processing words for {len(sentences)} sentences in case {case_id}")
                
                for sentence in sentences:
                    sentence_stats = self.process_sentence_words(
                        case_id=case_id,
                        chunk_id=sentence.chunk_id,
                        sentence_id=sentence.sentence_id,
                        sentence_text=sentence.text,
                        document_id=document_id
                    )
                    
                    total_words += sentence_stats['words_processed']
                    
                    # Get unique words from this sentence
                    tokens = self.tokenize_text(sentence.text)
                    unique_words.update(tokens)
                
                logger.info(f"Completed word processing: {total_words} total words, {len(unique_words)} unique")
                
                return {
                    'total_words': total_words,
                    'unique_words': len(unique_words),
                    'sentences_processed': len(sentences)
                }
                
        except Exception as e:
            logger.error(f"Error processing sentence words for case {case_id}: {e}")
            return {
                'total_words': 0,
                'unique_words': 0,
                'sentences_processed': 0
            }
    
    def _insert_word_occurrences(self, word_occurrences: List[Dict]) -> None:
        """Insert word occurrences in batch with new sentence-based schema
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        We now rely on tsvector columns on case_chunks and case_sentences for full-text search.
        This method is now a no-op but kept for API compatibility.
        """
        # word_occurrence table removed - using tsvector instead
        pass
    
    def update_word_document_frequencies(self, case_id: int) -> None:
        """
        Update document frequency counts for words in a case
        This should be called after processing all chunks for a case
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        This method is now a no-op but kept for API compatibility.
        """
        # word_occurrence table removed - using tsvector instead
        logger.debug(f"Skipping document frequency update for case {case_id} (word_occurrence table removed)")
    
    def find_word_positions(self, word: str, case_id: int = None) -> List[Dict]:
        """
        Find all positions of a word across cases/chunks using tsvector search.
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        Now uses tsvector-based search on case_sentences table.
        
        Args:
            word: Word to search for
            case_id: Optional case ID to limit search
            
        Returns:
            List of sentence information where word appears
        """
        with self.db.connect() as conn:
            base_query = """
                SELECT cs.case_id, cs.chunk_id, cs.sentence_id, cs.sentence_text
                FROM case_sentences cs
                WHERE cs.tsv @@ plainto_tsquery('english', :word)
            """
            
            params = {'word': word.lower()}
            
            if case_id:
                base_query += " AND cs.case_id = :case_id"
                params['case_id'] = case_id
            
            base_query += " ORDER BY cs.case_id, cs.chunk_id, cs.sentence_order LIMIT 1000"
            
            result = conn.execute(text(base_query), params)
            
            return [
                {
                    'case_id': row.case_id,
                    'chunk_id': row.chunk_id,
                    'sentence_id': row.sentence_id,
                    'word': word.lower()
                }
                for row in result
            ]
    
    def find_phrase_positions(self, phrase: str, case_id: int = None) -> List[Dict]:
        """
        Find all positions where a phrase occurs using tsvector search.
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        Now uses tsvector-based search on case_sentences table.
        
        Args:
            phrase: Phrase to search for (space-separated words)
            case_id: Optional case ID to limit search
            
        Returns:
            List of sentence information where phrase appears
        """
        with self.db.connect() as conn:
            # Use phraseto_tsquery for phrase matching
            base_query = """
                SELECT cs.case_id, cs.chunk_id, cs.sentence_id, cs.sentence_text
                FROM case_sentences cs
                WHERE cs.tsv @@ phraseto_tsquery('english', :phrase)
            """
            
            params = {'phrase': phrase.lower()}
            
            if case_id:
                base_query += " AND cs.case_id = :case_id"
                params['case_id'] = case_id
            
            base_query += " ORDER BY cs.case_id, cs.chunk_id, cs.sentence_order LIMIT 1000"
            
            result = conn.execute(text(base_query), params)
            
            return [
                {
                    'case_id': row.case_id,
                    'chunk_id': row.chunk_id,
                    'sentence_id': row.sentence_id,
                    'phrase': phrase.lower()
                }
                for row in result
            ]
