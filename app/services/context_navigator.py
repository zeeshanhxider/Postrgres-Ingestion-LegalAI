"""
Context Navigator: Word-to-Document Navigation Service
Enables hierarchical navigation from word → context → chunk → document
"""

import logging
from typing import List, Dict, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

class ContextNavigator:
    """Navigate from words to documents through the data hierarchy"""
    
    def __init__(self, db_engine: Engine):
        self.db = db_engine
    
    def find_word_in_context(self, word: str, case_id: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """
        Find all occurrences of a word with immediate context
        
        Args:
            word: Word to search for
            case_id: Optional case filter
            limit: Maximum results
            
        Returns:
            List of word occurrences with context info
        """
        with self.db.connect() as conn:
            base_query = """
                SELECT 
                    wo.case_id,
                    wo.chunk_id, 
                    wo.position,
                    wd.word,
                    cc.section,
                    cc.chunk_order,
                    c.title as case_title,
                    c.court,
                    c.filing_date,
                    substring(cc.text from 1 for 200) as chunk_preview
                FROM word_occurrence wo
                JOIN word_dictionary wd ON wo.word_id = wd.word_id
                JOIN case_chunks cc ON wo.chunk_id = cc.chunk_id
                JOIN cases c ON wo.case_id = c.case_id
                WHERE wd.word = :word
            """
            
            params = {'word': word.lower()}
            
            if case_id:
                base_query += " AND wo.case_id = :case_id"
                params['case_id'] = case_id
            
            base_query += " ORDER BY wo.case_id, cc.chunk_order, wo.position LIMIT :limit"
            params['limit'] = limit
            
            result = conn.execute(text(base_query), params)
            
            return [
                {
                    'case_id': row.case_id,
                    'chunk_id': str(row.chunk_id),
                    'position': row.position,
                    'word': row.word,
                    'section': row.section,
                    'chunk_order': row.chunk_order,
                    'case_title': row.case_title,
                    'court': row.court,
                    'filing_date': row.filing_date,
                    'chunk_preview': row.chunk_preview
                }
                for row in result
            ]
    
    def get_word_context_window(self, word: str, chunk_id: int, window_size: int = 10) -> Dict:
        """
        Get surrounding words around a target word in a chunk
        
        Args:
            word: Target word
            chunk_id: Chunk containing the word
            window_size: Number of words before/after
            
        Returns:
            Dictionary with context words and metadata
        """
        with self.db.connect() as conn:
            query = text("""
                WITH target_word AS (
                    SELECT wo.chunk_id, wo.position as target_position
                    FROM word_occurrence wo
                    JOIN word_dictionary wd ON wo.word_id = wd.word_id
                    WHERE wd.word = :word AND wo.chunk_id = :chunk_id
                    LIMIT 1
                ),
                context_words AS (
                    SELECT 
                        wd.word,
                        wo.position,
                        wo.position - tw.target_position as relative_position
                    FROM word_occurrence wo
                    JOIN word_dictionary wd ON wo.word_id = wd.word_id
                    CROSS JOIN target_word tw
                    WHERE wo.chunk_id = :chunk_id
                      AND wo.position BETWEEN (tw.target_position - :window_size) 
                                          AND (tw.target_position + :window_size)
                    ORDER BY wo.position
                )
                SELECT 
                    word,
                    position,
                    relative_position,
                    CASE 
                        WHEN relative_position = 0 THEN 'TARGET'
                        WHEN relative_position < 0 THEN 'BEFORE'
                        ELSE 'AFTER'
                    END as context_type
                FROM context_words
                ORDER BY position
            """)
            
            result = conn.execute(query, {
                'word': word.lower(),
                'chunk_id': chunk_id,
                'window_size': window_size
            })
            
            context_words = []
            target_position = None
            
            for row in result:
                word_info = {
                    'word': row.word,
                    'position': row.position,
                    'relative_position': row.relative_position,
                    'context_type': row.context_type
                }
                context_words.append(word_info)
                
                if row.context_type == 'TARGET':
                    target_position = row.position
            
            # Reconstruct the context sentence
            context_sentence = ' '.join([w['word'] for w in context_words])
            
            return {
                'target_word': word,
                'target_position': target_position,
                'chunk_id': chunk_id,
                'context_words': context_words,
                'context_sentence': context_sentence,
                'window_size': window_size
            }
    
    def get_chunk_with_highlights(self, chunk_id: int, highlight_words: List[str] = None) -> Dict:
        """
        Get full chunk text with optional word highlighting
        
        Args:
            chunk_id: Target chunk ID
            highlight_words: Words to highlight in the text
            
        Returns:
            Chunk data with highlighting info
        """
        with self.db.connect() as conn:
            # Get chunk data
            chunk_query = text("""
                SELECT 
                    cc.chunk_id,
                    cc.case_id,
                    cc.chunk_order,
                    cc.section,
                    cc.text,
                    c.title as case_title,
                    c.court,
                    c.filing_date,
                    COUNT(wo.word_id) as total_words
                FROM case_chunks cc
                JOIN cases c ON cc.case_id = c.case_id
                LEFT JOIN word_occurrence wo ON cc.chunk_id = wo.chunk_id
                WHERE cc.chunk_id = :chunk_id
                GROUP BY cc.chunk_id, cc.case_id, cc.chunk_order, cc.section, 
                         cc.text, c.title, c.court, c.filing_date
            """)
            
            chunk_result = conn.execute(chunk_query, {'chunk_id': chunk_id})
            chunk_row = chunk_result.fetchone()
            
            if not chunk_row:
                return None
            
            chunk_data = {
                'chunk_id': str(chunk_row.chunk_id),
                'case_id': chunk_row.case_id,
                'chunk_order': chunk_row.chunk_order,
                'section': chunk_row.section,
                'text': chunk_row.text,
                'case_title': chunk_row.case_title,
                'court': chunk_row.court,
                'filing_date': chunk_row.filing_date,
                'total_words': chunk_row.total_words
            }
            
            # Get word positions for highlighting
            if highlight_words:
                word_positions = {}
                for word in highlight_words:
                    pos_query = text("""
                        SELECT wo.position
                        FROM word_occurrence wo
                        JOIN word_dictionary wd ON wo.word_id = wd.word_id
                        WHERE wd.word = :word AND wo.chunk_id = :chunk_id
                        ORDER BY wo.position
                    """)
                    
                    pos_result = conn.execute(pos_query, {
                        'word': word.lower(),
                        'chunk_id': chunk_id
                    })
                    
                    positions = [row.position for row in pos_result]
                    if positions:
                        word_positions[word] = positions
                
                chunk_data['highlighted_words'] = word_positions
            
            return chunk_data
    
    def get_adjacent_chunks(self, chunk_id: int, range_before: int = 10, range_after: int = 10) -> List[Dict]:
        """
        Get chunks surrounding the target chunk
        
        Args:
            chunk_id: Target chunk ID
            range_before: Number of chunks before target
            range_after: Number of chunks after target
            
        Returns:
            List of adjacent chunks with position info
        """
        with self.db.connect() as conn:
            query = text("""
                WITH target_chunk AS (
                    SELECT case_id, chunk_order
                    FROM case_chunks 
                    WHERE chunk_id = :chunk_id
                )
                SELECT 
                    cc.chunk_id,
                    cc.chunk_order,
                    cc.section,
                    cc.text,
                    substring(cc.text from 1 for 300) as preview,
                    CASE 
                        WHEN cc.chunk_order < tc.chunk_order THEN 'BEFORE'
                        WHEN cc.chunk_order = tc.chunk_order THEN 'TARGET'
                        ELSE 'AFTER'
                    END as position_type,
                    ABS(cc.chunk_order - tc.chunk_order) as distance_from_target
                FROM case_chunks cc
                CROSS JOIN target_chunk tc
                WHERE cc.case_id = tc.case_id
                  AND cc.chunk_order BETWEEN (tc.chunk_order - :range_before) 
                                         AND (tc.chunk_order + :range_after)
                ORDER BY cc.chunk_order
            """)
            
            result = conn.execute(query, {
                'chunk_id': chunk_id,
                'range_before': range_before,
                'range_after': range_after
            })
            
            return [
                {
                    'chunk_id': str(row.chunk_id),
                    'chunk_order': row.chunk_order,
                    'section': row.section,
                    'text': row.text,
                    'preview': row.preview,
                    'position_type': row.position_type,
                    'distance_from_target': row.distance_from_target
                }
                for row in result
            ]
    
    def get_document_from_chunk(self, chunk_id: int) -> Dict:
        """
        Get complete document information from a chunk
        
        Args:
            chunk_id: Any chunk ID in the document
            
        Returns:
            Complete document data with statistics
        """
        with self.db.connect() as conn:
            query = text("""
                SELECT 
                    c.*,
                    -- Document statistics
                    COUNT(DISTINCT cc.chunk_id) as total_chunks,
                    COUNT(DISTINCT wo.word_id) as unique_words,
                    COUNT(wo.word_id) as total_words,
                    COUNT(DISTINCT cp.phrase) as unique_phrases,
                    -- AI-extracted entities
                    COUNT(DISTINCT p.party_id) as parties_count,
                    COUNT(DISTINCT a.attorney_id) as attorneys_count,
                    COUNT(DISTINCT i.issue_id) as issues_count,
                    COUNT(DISTINCT d.decision_id) as decisions_count
                FROM cases c
                LEFT JOIN case_chunks cc ON c.case_id = cc.case_id
                LEFT JOIN word_occurrence wo ON c.case_id = wo.case_id
                LEFT JOIN case_phrases cp ON c.case_id = cp.case_id
                LEFT JOIN parties p ON c.case_id = p.case_id
                LEFT JOIN attorneys a ON c.case_id = a.case_id
                LEFT JOIN issues i ON c.case_id = i.case_id
                LEFT JOIN decisions d ON c.case_id = d.case_id
                WHERE c.case_id = (
                    SELECT case_id FROM case_chunks WHERE chunk_id = :chunk_id
                )
                GROUP BY c.case_id
            """)
            
            result = conn.execute(query, {'chunk_id': chunk_id})
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                'case_id': row.case_id,
                'title': row.title,
                'court': row.court,
                'court_level': row.court_level,
                'district': row.district,
                'county': row.county,
                'docket_number': row.docket_number,
                'filing_date': row.filing_date,
                'published': row.published,
                'summary': row.summary,
                'full_text': row.full_text,
                'source_url': row.source_url,
                'source_file': row.source_file,
                'source_file_path': row.source_file_path,
                'created_at': row.created_at,
                'updated_at': row.updated_at,
                # Statistics
                'statistics': {
                    'total_chunks': row.total_chunks,
                    'unique_words': row.unique_words,
                    'total_words': row.total_words,
                    'unique_phrases': row.unique_phrases,
                    'parties_count': row.parties_count,
                    'attorneys_count': row.attorneys_count,
                    'issues_count': row.issues_count,
                    'decisions_count': row.decisions_count
                }
            }
    
    def navigate_word_to_document(self, word: str, case_id: Optional[str] = None) -> List[Dict]:
        """
        Complete navigation from word to full document context
        
        Args:
            word: Starting word
            case_id: Optional case filter
            
        Returns:
            Complete navigation data for each word occurrence
        """
        # Step 1: Find all word occurrences
        word_occurrences = self.find_word_in_context(word, case_id)
        
        navigation_results = []
        
        for occurrence in word_occurrences:
            chunk_id = occurrence['chunk_id']
            
            # Step 2: Get word context
            context = self.get_word_context_window(word, chunk_id)
            
            # Step 3: Get full chunk
            chunk_data = self.get_chunk_with_highlights(chunk_id, [word])
            
            # Step 4: Get adjacent chunks
            adjacent_chunks = self.get_adjacent_chunks(chunk_id)
            
            # Step 5: Get document
            document = self.get_document_from_chunk(chunk_id)
            
            navigation_results.append({
                'word_occurrence': occurrence,
                'context_window': context,
                'target_chunk': chunk_data,
                'adjacent_chunks': adjacent_chunks,
                'full_document': document
            })
        
        return navigation_results
