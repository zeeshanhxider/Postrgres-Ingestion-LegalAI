"""
RAG Processor - Main orchestrator for all RAG pipeline components.

Coordinates chunking, sentence processing, word indexing, phrase extraction,
and embedding generation with configurable options.
"""
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.engine import Engine
import requests

from .config import Config
from .chunker import LegalTextChunker, TextChunk
from .sentence_processor import SentenceProcessor
from .word_processor import WordProcessor
from .phrase_extractor import PhraseExtractor
from .dimension_service import DimensionService

logger = logging.getLogger(__name__)

# Global lock for Ollama API calls to prevent overload
_ollama_lock = threading.Lock()


class ChunkEmbeddingMode(Enum):
    """Options for chunk-level embedding generation."""
    ALL = "all"           # Generate embeddings for all chunks
    IMPORTANT = "important"  # Only ANALYSIS, HOLDING, FACTS sections
    NONE = "none"         # No chunk embeddings (rely on case-level only)


class PhraseFilterMode(Enum):
    """Options for phrase filtering strictness."""
    STRICT = "strict"     # Only phrases with legal terms
    RELAXED = "relaxed"   # All meaningful phrases


@dataclass
class RAGProcessingResult:
    """Result of RAG processing for a case."""
    case_id: int
    chunks_created: int
    sentences_created: int
    words_indexed: int
    phrases_extracted: int
    embeddings_generated: int
    errors: List[str]


class RAGProcessor:
    """
    Main orchestrator for RAG processing pipeline.
    
    Handles:
    - Text chunking with section awareness
    - Sentence extraction and indexing
    - Word dictionary and occurrence tracking
    - Legal phrase extraction
    - Chunk-level embedding generation
    """
    
    # Sections considered "important" for selective embedding
    IMPORTANT_SECTIONS = {"ANALYSIS", "HOLDING", "FACTS"}
    
    def __init__(
        self,
        db_engine: Engine,
        chunk_embedding_mode: ChunkEmbeddingMode = ChunkEmbeddingMode.ALL,
        phrase_filter_mode: PhraseFilterMode = PhraseFilterMode.STRICT,
        batch_size: int = 100,
        embedding_batch_size: int = 25
    ):
        """
        Initialize RAG processor.
        
        Args:
            db_engine: SQLAlchemy database engine
            chunk_embedding_mode: How to handle chunk embeddings (default: ALL)
            phrase_filter_mode: Strictness of phrase filtering
            batch_size: Batch size for database inserts
            embedding_batch_size: Batch size for embedding API calls
        """
        self.db = db_engine
        self.chunk_embedding_mode = chunk_embedding_mode
        self.phrase_filter_mode = phrase_filter_mode
        self.batch_size = batch_size
        self.embedding_batch_size = embedding_batch_size
        
        # Initialize sub-processors
        self.chunker = LegalTextChunker()
        self.sentence_processor = SentenceProcessor(db_engine)
        self.word_processor = WordProcessor(db_engine, batch_size=batch_size)
        self.phrase_extractor = PhraseExtractor(
            db_engine=db_engine,
            strict_filtering=(phrase_filter_mode == PhraseFilterMode.STRICT)
        )
        self.dimension_service = DimensionService(db_engine)
        
        logger.info(
            f"RAGProcessor initialized: chunk_embedding={chunk_embedding_mode.value}, "
            f"phrase_filter={phrase_filter_mode.value}"
        )
    
    def process_case(
        self,
        case_id: int,
        full_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[int] = None
    ) -> RAGProcessingResult:
        """
        Process a case through the complete RAG pipeline.
        
        Args:
            case_id: Database ID of the case
            full_text: Full text content of the case
            metadata: Optional metadata dict (for dimension resolution)
            document_id: Optional document ID to associate with chunks/sentences
            
        Returns:
            RAGProcessingResult with processing statistics
        """
        errors = []
        chunks_created = 0
        sentences_created = 0
        words_indexed = 0
        phrases_extracted = 0
        embeddings_generated = 0
        
        try:
            logger.info(f"Starting RAG processing for case {case_id}")
            
            # Step 1: Create chunks
            chunks = self.chunker.chunk_text(full_text)
            logger.info(f"Created {len(chunks)} chunks")
            
            # Step 2: Insert chunks and get IDs
            chunk_ids = self._insert_chunks(case_id, chunks, document_id=document_id)
            chunks_created = len(chunk_ids)
            
            # Step 3: Generate chunk embeddings based on mode
            if self.chunk_embedding_mode != ChunkEmbeddingMode.NONE:
                embeddings_generated = self._generate_chunk_embeddings(
                    chunks, chunk_ids
                )
            
            # Step 4: Process sentences for each chunk
            global_sentence_order = 0
            for chunk, chunk_id in zip(chunks, chunk_ids):
                try:
                    sentence_results = self.sentence_processor.process_chunk_sentences(
                        chunk_id, chunk.text, case_id=case_id,
                        document_id=document_id,
                        global_sentence_counter=global_sentence_order
                    )
                    sentence_ids = [s['id'] for s in sentence_results]
                    sentences_created += len(sentence_ids)
                    global_sentence_order += len(sentence_ids)
                    
                    # Step 5: Process words for each sentence
                    for sentence_result in sentence_results:
                        word_count = self.word_processor.process_sentence_words_simple(
                            sentence_result['id'], sentence_result['text']
                        )
                        words_indexed += word_count
                        
                except Exception as e:
                    logger.error(f"Error processing chunk {chunk_id}: {e}")
                    errors.append(f"Chunk {chunk_id}: {str(e)}")
            
            # Flush any remaining word occurrences
            self.word_processor.flush()
            
            # Step 6: Extract phrases for the entire case
            try:
                phrase_count = self.phrase_extractor.process_case_phrases_from_text(
                    case_id, full_text, document_id=document_id
                )
                phrases_extracted = phrase_count
            except Exception as e:
                logger.error(f"Error extracting phrases: {e}")
                errors.append(f"Phrase extraction: {str(e)}")
            
            logger.info(
                f"RAG processing complete for case {case_id}: "
                f"{chunks_created} chunks, {sentences_created} sentences, "
                f"{words_indexed} words, {phrases_extracted} phrases, "
                f"{embeddings_generated} embeddings"
            )
            
        except Exception as e:
            logger.error(f"RAG processing failed for case {case_id}: {e}")
            errors.append(f"Fatal: {str(e)}")
        
        return RAGProcessingResult(
            case_id=case_id,
            chunks_created=chunks_created,
            sentences_created=sentences_created,
            words_indexed=words_indexed,
            phrases_extracted=phrases_extracted,
            embeddings_generated=embeddings_generated,
            errors=errors
        )
    
    def _insert_chunks(
        self,
        case_id: int,
        chunks: List[TextChunk],
        document_id: Optional[int] = None
    ) -> List[int]:
        """Insert chunks into database and return their IDs."""
        chunk_ids = []
        
        with self.db.connect() as conn:
            for chunk in chunks:
                result = conn.execute(text("""
                    INSERT INTO case_chunks (
                        case_id, document_id, chunk_order, section, text
                    )
                    VALUES (:case_id, :document_id, :chunk_order, :section, :text)
                    RETURNING chunk_id
                """), {
                    'case_id': case_id,
                    'document_id': document_id,
                    'chunk_order': chunk.chunk_index,
                    'section': chunk.section_type,
                    'text': chunk.text
                })
                chunk_ids.append(result.fetchone()[0])
            
            conn.commit()
            
        logger.debug(f"Inserted {len(chunk_ids)} chunks for case {case_id}")
        return chunk_ids
    
    def _generate_chunk_embeddings(
        self,
        chunks: List[TextChunk],
        chunk_ids: List[int]
    ) -> int:
        """Generate embeddings for chunks based on mode."""
        embeddings_generated = 0
        
        # Filter chunks based on mode
        if self.chunk_embedding_mode == ChunkEmbeddingMode.IMPORTANT:
            eligible = [
                (chunk, chunk_id) 
                for chunk, chunk_id in zip(chunks, chunk_ids)
                if chunk.section_type in self.IMPORTANT_SECTIONS
            ]
        else:  # ALL mode
            eligible = list(zip(chunks, chunk_ids))
        
        if not eligible:
            return 0
        
        logger.info(f"Generating embeddings for {len(eligible)} chunks")
        
        with self.db.connect() as conn:
            # Process in batches
            for i in range(0, len(eligible), self.embedding_batch_size):
                batch = eligible[i:i + self.embedding_batch_size]
                
                for chunk, chunk_id in batch:
                    try:
                        embedding = self._generate_embedding_sync(chunk.text)
                        if embedding:
                            # Insert into embeddings table (not update case_chunks)
                            conn.execute(text("""
                                INSERT INTO embeddings (
                                    case_id, chunk_id, text, embedding,
                                    chunk_order, section
                                )
                                SELECT case_id, chunk_id, text, :embedding,
                                       chunk_order, section
                                FROM case_chunks WHERE chunk_id = :chunk_id
                            """), {'embedding': embedding, 'chunk_id': chunk_id})
                            embeddings_generated += 1
                    except Exception as e:
                        logger.warning(f"Failed to generate embedding for chunk {chunk_id}: {e}")
            
            conn.commit()
        
        return embeddings_generated
    
    def _generate_embedding_sync(self, text_content: str) -> Optional[List[float]]:
        """Generate embedding for text using Ollama (synchronous, thread-safe)."""
        # Use lock to prevent overwhelming Ollama with concurrent requests
        with _ollama_lock:
            try:
                response = requests.post(
                    f"{Config.OLLAMA_BASE_URL}/api/embed",
                    json={
                        "model": Config.OLLAMA_EMBEDDING_MODEL,
                        "input": text_content[:4000]  # Truncate to 4k chars for faster embedding
                    },
                    timeout=60  # Increased timeout for embedding generation
                )
                response.raise_for_status()
                result = response.json()
                # New API returns "embeddings" array, old API returns "embedding"
                embeddings = result.get("embeddings")
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                return result.get("embedding")
            except requests.exceptions.Timeout:
                logger.warning(f"Embedding generation timed out")
                return None
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                return None
    
    # Alias for backward compatibility
    def process_case_sync(
        self,
        case_id: int,
        full_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[int] = None
    ) -> RAGProcessingResult:
        """Synchronous version of process_case (same as process_case now)."""
        return self.process_case(case_id, full_text, metadata, document_id=document_id)


# Alias for backward compatibility
SyncRAGProcessor = RAGProcessor


def create_rag_processor(
    db_engine: Engine,
    chunk_embedding_mode: str = "all",
    phrase_filter_mode: str = "strict",
    batch_size: int = 50
) -> RAGProcessor:
    """
    Factory function to create RAG processor with string arguments.
    
    Args:
        db_engine: SQLAlchemy database engine
        chunk_embedding_mode: "all", "important", or "none"
        phrase_filter_mode: "strict" or "relaxed"
        batch_size: Batch size for database operations
        
    Returns:
        Configured RAGProcessor instance
    """
    # Convert string to enum
    try:
        embedding_mode = ChunkEmbeddingMode(chunk_embedding_mode.lower())
    except ValueError:
        logger.warning(f"Invalid chunk_embedding_mode '{chunk_embedding_mode}', using 'all'")
        embedding_mode = ChunkEmbeddingMode.ALL
    
    try:
        filter_mode = PhraseFilterMode(phrase_filter_mode.lower())
    except ValueError:
        logger.warning(f"Invalid phrase_filter_mode '{phrase_filter_mode}', using 'strict'")
        filter_mode = PhraseFilterMode.STRICT
    
    return RAGProcessor(
        db_engine=db_engine,
        chunk_embedding_mode=embedding_mode,
        phrase_filter_mode=filter_mode,
        batch_size=batch_size
    )
