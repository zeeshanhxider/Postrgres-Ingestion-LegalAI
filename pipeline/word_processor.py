"""
Word Processor
Handles word dictionary and occurrence tracking for precise search.
Enables word-level indexing for RAG.
"""

import re
import logging
from typing import List, Dict, Set, Optional
from collections import Counter
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class WordProcessor:
    """Process text for word dictionary and occurrence tracking."""
    
    # Common stop words to skip
    STOP_WORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these',
        'those', 'it', 'its', 'he', 'she', 'they', 'we', 'you', 'i', 'me', 'him',
        'her', 'us', 'them', 'my', 'your', 'his', 'our', 'their', 'which', 'who',
        'whom', 'what', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
        'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now',
        'here', 'there', 'then', 'once', 'if', 'because', 'until', 'while', 'about',
        'against', 'between', 'into', 'through', 'during', 'before', 'after',
        'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again',
        'further', 'any', 'however', 'therefore', 'thus', 'hence', 'although'
    }
    
    def __init__(self, db_engine: Engine, batch_size: int = 500):
        self.db = db_engine
        self.batch_size = batch_size
        self._word_cache: Dict[str, int] = {}  # word -> word_id cache
        self._pending_occurrences: List[Dict] = []  # batch buffer
    
    def tokenize_text(self, text: str, remove_stop_words: bool = False) -> List[str]:
        """
        Tokenize text into words, preserving legal terminology.
        
        Args:
            text: Input text to tokenize
            remove_stop_words: Whether to filter out common stop words
            
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
        
        # Filter tokens
        filtered_tokens = []
        for token in tokens:
            # Keep if it's at least 2 characters and contains at least one letter
            if len(token) >= 2 and re.search(r'[a-zA-Z]', token):
                # Remove apostrophes at the end (possessives)
                token = re.sub(r"'s?$", "", token)
                if token:
                    if remove_stop_words and token in self.STOP_WORDS:
                        continue
                    filtered_tokens.append(token)
        
        return filtered_tokens
    
    def get_or_create_word_ids(self, conn, words: List[str]) -> Dict[str, int]:
        """
        Get or create word IDs for a list of words.
        Uses cache for performance.
        
        Args:
            conn: Database connection (within transaction)
            words: List of unique words
            
        Returns:
            Dictionary mapping word -> word_id
        """
        if not words:
            return {}
        
        word_to_id = {}
        words_to_lookup = []
        
        # Check cache first
        for word in words:
            if word in self._word_cache:
                word_to_id[word] = self._word_cache[word]
            else:
                words_to_lookup.append(word)
        
        if not words_to_lookup:
            return word_to_id
        
        # Batch lookup existing words
        unique_words = list(set(words_to_lookup))
        
        # Find existing words
        if unique_words:
            # Use ANY array syntax for batch lookup
            query = text("""
                SELECT word_id, word 
                FROM word_dictionary 
                WHERE word = ANY(:words)
            """)
            result = conn.execute(query, {'words': unique_words})
            
            for row in result:
                word_to_id[row.word] = row.word_id
                self._word_cache[row.word] = row.word_id
        
        # Create new words that don't exist
        new_words = [w for w in unique_words if w not in word_to_id]
        
        if new_words:
            insert_query = text("""
                INSERT INTO word_dictionary (word)
                VALUES (:word)
                ON CONFLICT (word) DO UPDATE SET word = EXCLUDED.word
                RETURNING word_id, word
            """)
            
            for word in new_words:
                try:
                    result = conn.execute(insert_query, {'word': word})
                    row = result.fetchone()
                    if row:
                        word_to_id[row.word] = row.word_id
                        self._word_cache[row.word] = row.word_id
                except Exception as e:
                    logger.warning(f"Failed to insert word '{word}': {e}")
        
        return word_to_id
    
    def process_sentence_words(
        self,
        conn,
        case_id: int,
        chunk_id: int,
        sentence_id: int,
        sentence_text: str,
        document_id: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Process a sentence's text for word occurrences.
        
        Args:
            conn: Database connection (within transaction)
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
        
        # Tokenize the sentence text (don't remove stop words for occurrence tracking)
        tokens = self.tokenize_text(sentence_text, remove_stop_words=False)
        
        if not tokens:
            return {'words_processed': 0, 'unique_words': 0}
        
        # Get unique words
        unique_words = list(set(tokens))
        
        # Get or create word IDs
        word_to_id = self.get_or_create_word_ids(conn, unique_words)
        
        # Create word occurrences (positions are relative to sentence)
        word_occurrences = []
        for position, word in enumerate(tokens):
            if word in word_to_id:
                word_occurrences.append({
                    'word_id': word_to_id[word],
                    'case_id': case_id,
                    'chunk_id': chunk_id,
                    'sentence_id': sentence_id,
                    'document_id': document_id,
                    'position': position
                })
        
        # Batch insert word occurrences
        if word_occurrences:
            self._insert_word_occurrences(conn, word_occurrences)
        
        return {
            'words_processed': len(tokens),
            'unique_words': len(unique_words),
            'occurrences_created': len(word_occurrences)
        }
    
    def _insert_word_occurrences(self, conn, occurrences: List[Dict]) -> None:
        """Insert word occurrences in batch.
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        We now rely on tsvector columns on case_chunks and case_sentences for full-text search.
        This method is now a no-op but kept for API compatibility.
        """
        # word_occurrence table removed - using tsvector instead
        pass
    
    def update_document_frequencies(self, conn, case_id: int) -> None:
        """
        Update document frequency counts for words in a case.
        Should be called after processing all sentences for a case.
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        This method is now a no-op but kept for API compatibility.
        """
        # word_occurrence table removed - using tsvector instead
        pass
    
    def clear_cache(self):
        """Clear the word ID cache."""
        self._word_cache = {}
    
    def find_word_positions(self, word: str, case_id: Optional[int] = None) -> List[Dict]:
        """
        Find all positions of a word across cases using tsvector search.
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        Now uses tsvector-based search on case_sentences table.
        
        Args:
            word: Word to search for
            case_id: Optional case ID to limit search
            
        Returns:
            List of sentence information where word appears
        """
        with self.db.connect() as conn:
            if case_id:
                query = text("""
                    SELECT cs.case_id, cs.chunk_id, cs.sentence_id, cs.sentence_text
                    FROM case_sentences cs
                    WHERE cs.tsv @@ plainto_tsquery('english', :word)
                      AND cs.case_id = :case_id
                    ORDER BY cs.chunk_id, cs.sentence_order
                """)
                result = conn.execute(query, {'word': word.lower(), 'case_id': case_id})
            else:
                query = text("""
                    SELECT cs.case_id, cs.chunk_id, cs.sentence_id, cs.sentence_text
                    FROM case_sentences cs
                    WHERE cs.tsv @@ plainto_tsquery('english', :word)
                    ORDER BY cs.case_id, cs.chunk_id, cs.sentence_order
                    LIMIT 1000
                """)
                result = conn.execute(query, {'word': word.lower()})
            
            return [
                {
                    'case_id': row.case_id,
                    'chunk_id': row.chunk_id,
                    'sentence_id': row.sentence_id,
                    'word': word.lower()
                }
                for row in result
            ]
    
    def process_sentence_words_simple(
        self,
        sentence_id: int,
        sentence_text: str
    ) -> int:
        """
        Simplified method to process a sentence's words.
        Uses the stored db engine and batches operations.
        
        Args:
            sentence_id: Sentence identifier
            sentence_text: Sentence text content
            
        Returns:
            Number of words processed
        """
        if not sentence_text:
            return 0
        
        # Tokenize
        tokens = self.tokenize_text(sentence_text, remove_stop_words=False)
        
        if not tokens:
            return 0
        
        # Get unique words and create IDs
        unique_words = list(set(tokens))
        
        with self.db.connect() as conn:
            word_to_id = self.get_or_create_word_ids(conn, unique_words)
            conn.commit()
        
        # Look up case_id and chunk_id from sentence
        with self.db.connect() as conn:
            result = conn.execute(text(
                "SELECT case_id, chunk_id FROM case_sentences WHERE sentence_id = :sid"
            ), {'sid': sentence_id})
            row = result.fetchone()
            if not row:
                return 0
            case_id, chunk_id = row[0], row[1]
        
        # Create word occurrences
        for position, word in enumerate(tokens):
            if word in word_to_id:
                self._pending_occurrences.append({
                    'word_id': word_to_id[word],
                    'case_id': case_id,
                    'chunk_id': chunk_id,
                    'sentence_id': sentence_id,
                    'document_id': None,
                    'position': position
                })
        
        # Flush if batch is full
        if len(self._pending_occurrences) >= self.batch_size:
            self.flush()
        
        return len(tokens)
    
    def flush(self):
        """Flush pending word occurrences to database using bulk insert.
        
        NOTE: word_occurrence table was dropped in scalability migration (018).
        We now rely on tsvector columns on case_chunks and case_sentences for full-text search.
        This method now just clears the pending buffer.
        """
        # word_occurrence table removed - using tsvector instead
        # Just clear the buffer
        self._pending_occurrences = []
