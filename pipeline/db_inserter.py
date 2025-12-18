"""
Database Inserter - Clean SQL insertion for extracted cases
Maps ExtractedCase to the database schema.

Integrates with RAG processor for full indexing pipeline.
"""

import os
import re
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import psycopg2

from .models import ExtractedCase, Party, Attorney, Judge, Citation, Statute, Issue
from .dimension_service import DimensionService

logger = logging.getLogger(__name__)

# Global lock for Ollama API calls to prevent overload
_ollama_embedding_lock = threading.Lock()


def generate_embedding(text: str, model: str = None) -> Optional[List[float]]:
    """
    Generate embedding using Ollama (thread-safe).
    Returns 1024-dim vector for mxbai-embed-large.
    """
    with _ollama_embedding_lock:
        try:
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError:
                from langchain_community.embeddings import OllamaEmbeddings
            
            ollama_model = model or os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")
            ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            embeddings = OllamaEmbeddings(model=ollama_model, base_url=ollama_base_url)
            return embeddings.embed_query(text)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None


class DatabaseInserter:
    """
    Insert extracted case data into PostgreSQL database.
    Uses simple, direct SQL - no ORM complexity.
    
    Integrates with DimensionService for FK resolution and
    optionally with RAGProcessor for full indexing.
    """
    
    def __init__(self, db_engine: Engine, enable_rag: bool = True):
        """
        Initialize with database engine.
        
        Args:
            db_engine: SQLAlchemy engine instance
            enable_rag: Whether to enable RAG processing
        """
        self.db = db_engine
        self.enable_rag = enable_rag
        self._dimension_service = None
        self._rag_processor = None
    
    @classmethod
    def from_url(cls, database_url: str, enable_rag: bool = True) -> 'DatabaseInserter':
        """
        Create inserter from database URL with connection pooling.
        
        Args:
            database_url: PostgreSQL connection string
            enable_rag: Whether to enable RAG processing
        """
        # Connection pooling for better performance
        engine = create_engine(
            database_url,
            pool_size=5,           # Base pool size
            max_overflow=10,       # Allow 10 extra connections
            pool_pre_ping=True,    # Verify connections before use
            pool_recycle=3600      # Recycle connections after 1 hour
        )
        return cls(engine, enable_rag=enable_rag)
    
    def _get_psycopg2_connection(self):
        """Get a psycopg2 connection from SQLAlchemy URL."""
        url = self.db.url
        return psycopg2.connect(
            host=url.host,
            port=url.port or 5432,
            database=url.database,
            user=url.username,
            password=url.password
        )
    
    def _get_dimension_service(self, conn) -> DimensionService:
        """Get or create dimension service."""
        if self._dimension_service is None:
            # DimensionService uses SQLAlchemy Engine, not psycopg2
            self._dimension_service = DimensionService(self.db)
        return self._dimension_service
    
    def configure_rag(
        self,
        chunk_embedding_mode: str = "all",
        phrase_filter_mode: str = "strict"
    ):
        """
        Configure RAG processor options.
        
        Args:
            chunk_embedding_mode: "all", "important", or "none"
            phrase_filter_mode: "strict" or "relaxed"
        """
        from .rag_processor import create_rag_processor
        
        # Use SQLAlchemy engine directly
        self._rag_processor = create_rag_processor(
            self.db,
            chunk_embedding_mode=chunk_embedding_mode,
            phrase_filter_mode=phrase_filter_mode
        )
    
    def insert_case(self, case: ExtractedCase) -> Optional[int]:
        """
        Insert a complete case with all related entities.
        Optionally runs RAG processing for chunks, sentences, words, phrases.
        
        Args:
            case: ExtractedCase object with all data
            
        Returns:
            case_id if successful, None if failed, -1 if duplicate updated
        """
        try:
            with self.db.connect() as conn:
                trans = conn.begin()
                
                try:
                    # 1. Insert main case record (returns tuple: case_id, was_inserted)
                    case_id, was_inserted = self._insert_case_record(conn, case)
                    
                    if was_inserted:
                        logger.info(f"Inserted case with ID: {case_id}")
                    else:
                        # Duplicate - delete old related records before re-inserting
                        logger.info(f"Updating duplicate case {case_id} - clearing old related records")
                        self._clear_related_records(conn, case_id)
                    
                    # 2. Insert document record for the source PDF
                    document_id = self._insert_document(conn, case_id, case)
                    if document_id:
                        logger.info(f"Inserted document with ID: {document_id}")
                    
                    # 3. Insert parties
                    for party in case.parties:
                        self._insert_party(conn, case_id, party)
                    logger.info(f"Inserted {len(case.parties)} parties")
                    
                    # 4. Insert attorneys
                    for attorney in case.attorneys:
                        self._insert_attorney(conn, case_id, attorney)
                    logger.info(f"Inserted {len(case.attorneys)} attorneys")
                    
                    # 5. Insert judges
                    for judge in case.judges:
                        self._insert_judge(conn, case_id, judge)
                    logger.info(f"Inserted {len(case.judges)} judges")
                    
                    # 6. Insert citations
                    for citation in case.citations:
                        self._insert_citation(conn, case_id, citation)
                    logger.info(f"Inserted {len(case.citations)} citations")
                    
                    # 7. Insert statutes
                    for statute in case.statutes:
                        self._insert_statute(conn, case_id, statute)
                    logger.info(f"Inserted {len(case.statutes)} statutes")
                    
                    # 8. Insert issues and their arguments
                    for issue in case.issues:
                        issue_id = self._insert_issue(conn, case_id, issue)
                        # Insert arguments for this issue
                        if issue.appellant_argument:
                            self._insert_argument(conn, case_id, issue_id, 'appellant', issue.appellant_argument)
                        if issue.respondent_argument:
                            self._insert_argument(conn, case_id, issue_id, 'respondent', issue.respondent_argument)
                    logger.info(f"Inserted {len(case.issues)} issues with arguments")
                    
                    trans.commit()
                    logger.info(f"Successfully committed case {case_id}")
                    
                    # 9. Run RAG processing if enabled (pass document_id)
                    if self.enable_rag and case.full_text:
                        self._run_rag_processing(case_id, case, clear_existing=not was_inserted, document_id=document_id)
                    
                    # Return -1 for duplicates (updated), positive case_id for new inserts
                    return case_id if was_inserted else -1
                    
                except Exception as e:
                    trans.rollback()
                    logger.error(f"Insert failed, rolling back: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
    
    def _clear_related_records(self, conn, case_id: int):
        """Clear all related records for a case (for duplicate updates)."""
        tables = [
            'documents',
            'parties',
            'attorneys', 
            'case_judges',
            'citation_edges',
            'statute_citations',
            'issues_decisions'
        ]
        for table in tables:
            try:
                if table == 'citation_edges':
                    conn.execute(text(f"DELETE FROM {table} WHERE source_case_id = :case_id"), {'case_id': case_id})
                else:
                    conn.execute(text(f"DELETE FROM {table} WHERE case_id = :case_id"), {'case_id': case_id})
            except Exception as e:
                logger.warning(f"Could not clear {table} for case {case_id}: {e}")
    
    def _insert_document(self, conn, case_id: int, case: ExtractedCase) -> Optional[int]:
        """
        Insert a document record for the source PDF.
        
        Args:
            conn: Database connection
            case_id: Case ID
            case: ExtractedCase object
            
        Returns:
            document_id if successful, None otherwise
        """
        meta = case.metadata
        
        # Get stage_type_id and document_type_id
        dim_service = self._get_dimension_service(conn)
        stage_type_id = dim_service.get_stage_type_id(meta.opinion_type)
        document_type_id = dim_service.get_document_type_id('Opinion')
        
        # Calculate page count from full_text if available
        page_count = getattr(case, 'page_count', None)
        
        # Calculate file size if path available
        file_size = None
        if case.source_file_path:
            import os
            try:
                file_size = os.path.getsize(case.source_file_path)
            except:
                pass
        
        query = text("""
            INSERT INTO documents (
                case_id, stage_type_id, document_type_id,
                title, source_url, local_path,
                file_size, page_count, processing_status,
                created_at, updated_at
            ) VALUES (
                :case_id, :stage_type_id, :document_type_id,
                :title, :source_url, :local_path,
                :file_size, :page_count, :processing_status,
                :created_at, :updated_at
            )
            RETURNING document_id
        """)
        
        now = datetime.now()
        
        try:
            result = conn.execute(query, {
                'case_id': case_id,
                'stage_type_id': stage_type_id,
                'document_type_id': document_type_id,
                'title': meta.case_title or meta.pdf_filename or 'Unknown',
                'source_url': meta.pdf_url,
                'local_path': case.source_file_path,
                'file_size': file_size,
                'page_count': page_count,
                'processing_status': 'completed',
                'created_at': now,
                'updated_at': now,
            })
            row = result.fetchone()
            return row.document_id if row else None
        except Exception as e:
            logger.warning(f"Could not insert document: {e}")
            return None
    
    def _clear_rag_records(self, case_id: int):
        """Clear RAG records for a case (chunks, sentences, words, phrases)."""
        try:
            with self.db.connect() as conn:
                trans = conn.begin()
                try:
                    # Delete in order due to foreign keys
                    conn.execute(text("DELETE FROM word_occurrence WHERE sentence_id IN (SELECT sentence_id FROM case_sentences WHERE chunk_id IN (SELECT chunk_id FROM case_chunks WHERE case_id = :case_id))"), {'case_id': case_id})
                    conn.execute(text("DELETE FROM case_sentences WHERE chunk_id IN (SELECT chunk_id FROM case_chunks WHERE case_id = :case_id)"), {'case_id': case_id})
                    conn.execute(text("DELETE FROM case_phrases WHERE case_id = :case_id"), {'case_id': case_id})
                    conn.execute(text("DELETE FROM case_chunks WHERE case_id = :case_id"), {'case_id': case_id})
                    trans.commit()
                    logger.info(f"Cleared existing RAG records for case {case_id}")
                except Exception as e:
                    trans.rollback()
                    logger.warning(f"Could not clear RAG records for case {case_id}: {e}")
        except Exception as e:
            logger.warning(f"RAG cleanup connection error for case {case_id}: {e}")
    
    def _run_rag_processing(self, case_id: int, case: ExtractedCase, clear_existing: bool = False, document_id: Optional[int] = None):
        """
        Run RAG processing for a case.
        Creates chunks, sentences, words, phrases, and embeddings.
        
        Args:
            case_id: The case ID
            case: ExtractedCase object
            clear_existing: If True, clear existing RAG records first (for duplicates)
            document_id: The document ID to associate with RAG records
        """
        try:
            # Clear existing RAG records if this is a duplicate update
            if clear_existing:
                self._clear_rag_records(case_id)
            
            # Lazy-load RAG processor with default settings
            if self._rag_processor is None:
                from .rag_processor import create_rag_processor
                self._rag_processor = create_rag_processor(self.db)
            
            # Process the case
            result = self._rag_processor.process_case_sync(
                case_id,
                case.full_text,
                metadata=None,  # Could pass case.metadata if needed
                document_id=document_id
            )
            
            logger.info(
                f"RAG processing for case {case_id}: "
                f"{result.chunks_created} chunks, {result.sentences_created} sentences, "
                f"{result.words_indexed} words, {result.phrases_extracted} phrases, "
                f"{result.embeddings_generated} embeddings"
            )
            
            if result.errors:
                for err in result.errors:
                    logger.warning(f"RAG processing error: {err}")
                    
        except Exception as e:
            logger.error(f"RAG processing failed for case {case_id}: {e}")
            # Don't fail the whole insert if RAG fails
    
    def _insert_case_record(self, conn, case: ExtractedCase) -> int:
        """Insert main case record and return case_id."""
        
        meta = case.metadata
        
        # Generate embedding for full text
        full_embedding = None
        if case.full_text and len(case.full_text) > 100:
            # Use summary + first part of text for embedding (more semantic)
            embed_text = f"{case.summary}\n\n{case.full_text[:4000]}"
            logger.info("Generating full_embedding...")
            full_embedding = generate_embedding(embed_text)
            if full_embedding:
                logger.info(f"Generated {len(full_embedding)}-dim embedding")
        
        # Use DimensionService for all FK resolution
        dim_service = self._get_dimension_service(conn)
        dimension_ids = dim_service.resolve_all_dimensions(
            case_type=case.case_type,
            opinion_type=meta.opinion_type,
            court_level=meta.court_level,
            division=meta.division,
            county=case.county
        )
        
        query = text("""
            INSERT INTO cases (
                case_file_id, title, court_level, court, district, county,
                docket_number, source_docket_number,
                appeal_published_date, published,
                summary, full_text, full_embedding,
                source_url, case_info_url,
                overall_case_outcome, appeal_outcome,
                winner_legal_role, winner_personal_role,
                publication_status, 
                decision_year, decision_month,
                case_type, source_file, source_file_path,
                court_id, case_type_id, stage_type_id,
                extraction_timestamp, processing_status,
                created_at, updated_at
            ) VALUES (
                :case_file_id, :title, :court_level, :court, :district, :county,
                :docket_number, :source_docket_number,
                :appeal_published_date, :published,
                :summary, :full_text, :full_embedding,
                :source_url, :case_info_url,
                :overall_case_outcome, :appeal_outcome,
                :winner_legal_role, :winner_personal_role,
                :publication_status,
                :decision_year, :decision_month,
                :case_type, :source_file, :source_file_path,
                :court_id, :case_type_id, :stage_type_id,
                :extraction_timestamp, :processing_status,
                :created_at, :updated_at
            )
            ON CONFLICT (case_file_id, court_level) DO UPDATE SET
                title = EXCLUDED.title,
                court = EXCLUDED.court,
                district = EXCLUDED.district,
                county = EXCLUDED.county,
                docket_number = EXCLUDED.docket_number,
                source_docket_number = EXCLUDED.source_docket_number,
                appeal_published_date = EXCLUDED.appeal_published_date,
                published = EXCLUDED.published,
                summary = EXCLUDED.summary,
                full_text = EXCLUDED.full_text,
                full_embedding = EXCLUDED.full_embedding,
                source_url = EXCLUDED.source_url,
                case_info_url = EXCLUDED.case_info_url,
                overall_case_outcome = EXCLUDED.overall_case_outcome,
                appeal_outcome = EXCLUDED.appeal_outcome,
                winner_legal_role = EXCLUDED.winner_legal_role,
                winner_personal_role = EXCLUDED.winner_personal_role,
                publication_status = EXCLUDED.publication_status,
                decision_year = EXCLUDED.decision_year,
                decision_month = EXCLUDED.decision_month,
                case_type = EXCLUDED.case_type,
                source_file = EXCLUDED.source_file,
                source_file_path = EXCLUDED.source_file_path,
                court_id = EXCLUDED.court_id,
                case_type_id = EXCLUDED.case_type_id,
                stage_type_id = EXCLUDED.stage_type_id,
                extraction_timestamp = EXCLUDED.extraction_timestamp,
                processing_status = EXCLUDED.processing_status,
                updated_at = EXCLUDED.updated_at
            RETURNING case_id, (xmax = 0) AS inserted
        """)
        
        now = datetime.now()
        
        # Determine published boolean
        published = 'published' in (meta.publication_status or '').lower()
        
        # Build court name
        court = None
        if 'supreme' in (meta.court_level or '').lower():
            court = 'Washington State Supreme Court'
        elif 'appeals' in (meta.court_level or '').lower():
            division = meta.division or ''
            court = f'Washington Court of Appeals Division {division}'.strip()
        
        # Format docket number
        docket = meta.case_number
        if meta.division:
            docket = f"{meta.case_number}-{meta.division}"
        
        params = {
            'case_file_id': meta.case_number or None,
            'title': meta.case_title or 'Unknown',
            'court_level': meta.court_level or None,
            'court': court,
            'district': f"Division {meta.division}" if meta.division else None,
            'county': case.county,
            'docket_number': docket,
            'source_docket_number': case.source_docket_number,
            'appeal_published_date': case.opinion_filed_date or meta.file_date,
            'published': published,
            'summary': case.summary or None,
            'full_text': case.full_text,
            'full_embedding': full_embedding,
            'source_url': meta.pdf_url or None,
            'case_info_url': meta.case_info_url or None,
            'overall_case_outcome': case.appeal_outcome,
            'appeal_outcome': case.appeal_outcome,
            'winner_legal_role': case.winner_legal_role,
            'winner_personal_role': case.winner_personal_role,
            'publication_status': meta.publication_status or 'Published',
            'decision_year': meta.year,
            'decision_month': meta.month or None,
            'case_type': case.case_type or None,
            'source_file': meta.pdf_filename or None,
            'source_file_path': case.source_file_path,
            'court_id': dimension_ids.get('court_id'),
            'case_type_id': dimension_ids.get('case_type_id'),
            'stage_type_id': dimension_ids.get('stage_type_id'),
            'extraction_timestamp': case.extraction_timestamp or now,
            'processing_status': 'ai_processed' if case.extraction_successful else 'failed',
            'created_at': now,
            'updated_at': now,
        }
        
        result = conn.execute(query, params)
        row = result.fetchone()
        case_id = row.case_id
        was_inserted = row.inserted  # True if new insert, False if update
        
        if not was_inserted:
            logger.info(f"Duplicate case {meta.case_number} found - updated with newer data (case_id: {case_id})")
        
        return case_id, was_inserted
    
    def _get_or_create_court_id(self, conn, case: ExtractedCase, meta) -> Optional[int]:
        """
        Get or create court_id from courts_dim.
        
        Args:
            conn: Database connection
            case: ExtractedCase object
            meta: CaseMetadata object
            
        Returns:
            court_id from courts_dim, or None if not found/created
        """
        # Build court name
        court_name = None
        court_type = None
        level = meta.court_level
        district = f"Division {meta.division}" if meta.division else None
        
        if 'supreme' in (meta.court_level or '').lower():
            court_name = 'Washington State Supreme Court'
            court_type = 'Supreme Court'
        elif 'appeals' in (meta.court_level or '').lower():
            division = meta.division or ''
            court_name = f'Washington Court of Appeals Division {division}'.strip()
            court_type = 'Court of Appeals'
        
        if not court_name:
            return None
        
        # Try to find existing court
        get_court = text("SELECT court_id FROM courts_dim WHERE court = :court")
        result = conn.execute(get_court, {'court': court_name})
        row = result.fetchone()
        
        if row:
            return row.court_id
        
        # Create new court entry
        insert_court = text("""
            INSERT INTO courts_dim (court, level, jurisdiction, district, county, court_type)
            VALUES (:court, :level, :jurisdiction, :district, :county, :court_type)
            RETURNING court_id
        """)
        
        result = conn.execute(insert_court, {
            'court': court_name,
            'level': level,
            'jurisdiction': 'WA',
            'district': district,
            'county': case.county,
            'court_type': court_type,
        })
        
        new_row = result.fetchone()
        logger.info(f"Created new court in courts_dim: {court_name} (ID: {new_row.court_id})")
        return new_row.court_id
    
    def _insert_party(self, conn, case_id: int, party: Party) -> int:
        """Insert a party record."""
        query = text("""
            INSERT INTO parties (case_id, name, legal_role, personal_role, party_type, created_at)
            VALUES (:case_id, :name, :legal_role, :personal_role, :party_type, :created_at)
            RETURNING party_id
        """)
        
        result = conn.execute(query, {
            'case_id': case_id,
            'name': party.name,
            'legal_role': party.role,
            'personal_role': getattr(party, 'personal_role', None),
            'party_type': party.party_type,
            'created_at': datetime.now(),
        })
        
        return result.fetchone().party_id
    
    def _insert_attorney(self, conn, case_id: int, attorney: Attorney) -> int:
        """Insert an attorney record."""
        query = text("""
            INSERT INTO attorneys (case_id, name, firm_name, representing, created_at)
            VALUES (:case_id, :name, :firm_name, :representing, :created_at)
            RETURNING attorney_id
        """)
        
        result = conn.execute(query, {
            'case_id': case_id,
            'name': attorney.name,
            'firm_name': attorney.firm_name,
            'representing': attorney.representing,
            'created_at': datetime.now(),
        })
        
        return result.fetchone().attorney_id
    
    def _insert_judge(self, conn, case_id: int, judge: Judge) -> int:
        """
        Insert a judge record (uses normalized judges table).
        Creates judge if not exists, then links to case.
        Uses ON CONFLICT to handle race conditions in parallel processing.
        """
        # Get-or-create judge using ON CONFLICT to prevent race conditions
        # This is atomic and safe for parallel execution
        upsert_judge = text("""
            INSERT INTO judges (name) 
            VALUES (:name) 
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING judge_id
        """)
        result = conn.execute(upsert_judge, {'name': judge.name})
        judge_id = result.fetchone().judge_id
        
        # Link judge to case
        link_query = text("""
            INSERT INTO case_judges (case_id, judge_id, role, created_at)
            VALUES (:case_id, :judge_id, :role, :created_at)
            RETURNING id
        """)
        
        result = conn.execute(link_query, {
            'case_id': case_id,
            'judge_id': judge_id,
            'role': judge.role,
            'created_at': datetime.now(),
        })
        
        return result.fetchone().id
    
    def _insert_citation(self, conn, case_id: int, citation: Citation) -> int:
        """Insert a case citation edge."""
        query = text("""
            INSERT INTO citation_edges (
                source_case_id, target_case_citation, relationship, created_at
            ) VALUES (
                :source_case_id, :target_case_citation, :relationship, :created_at
            )
            ON CONFLICT (source_case_id, target_case_citation, COALESCE(pin_cite, '')) DO NOTHING
            RETURNING citation_id
        """)
        
        result = conn.execute(query, {
            'source_case_id': case_id,
            'target_case_citation': citation.full_citation,
            'relationship': citation.relationship or 'cited',
            'created_at': datetime.now(),
        })
        
        row = result.fetchone()
        return row.citation_id if row else 0
    
    def _parse_statute_citation(self, citation: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Parse statute citation like "RCW 69.50.4013(1)" into components.
        Returns (code, title, section, subsection)
        
        Examples:
        - "RCW 69.50.4013(1)" -> ("RCW", "69", "50.4013", "(1)")
        - "RCW 9.94A.525" -> ("RCW", "9", "94A.525", None)
        - "RCW 42.17A.765(3)(a)" -> ("RCW", "42", "17A.765", "(3)(a)")
        """
        # Pattern: RCW <title>.<section>(optional subsection with parentheses)
        pattern = r'^(RCW)\s+(\d+)\.([0-9A-Za-z.]+)((?:\([^)]+\))+)?'
        match = re.match(pattern, citation.strip(), re.IGNORECASE)
        
        if match:
            code = match.group(1).upper()
            title = match.group(2)
            section = match.group(3)
            # Keep parentheses in subsection: "(1)(a)" not "1)(a"
            subsection = match.group(4) if match.group(4) else None
            return (code, title, section, subsection)
        
        return (None, None, None, None)
    
    def _resolve_statute_id(self, conn, citation: str) -> Optional[int]:
        """
        Resolve statute citation to statute_id from statutes_dim.
        Tries multiple matching strategies:
        1. Exact match with subsection
        2. Match without subsection
        3. Partial section match (for cases like "9.94A" matching "9.94A.525")
        4. If no match found, CREATE the statute in statutes_dim
        """
        code, title, section, subsection = self._parse_statute_citation(citation)
        
        if not code or not title or not section:
            return None
        
        # Strategy 1: Try exact match with subsection
        if subsection:
            query = text("""
                SELECT statute_id FROM statutes_dim
                WHERE jurisdiction = 'WA'
                AND code = :code
                AND title = :title
                AND section = :section
                AND (subsection = :subsection OR subsection IS NULL)
                LIMIT 1
            """)
            result = conn.execute(query, {
                'code': code,
                'title': title,
                'section': section,
                'subsection': subsection
            })
            row = result.fetchone()
            if row:
                return row.statute_id
        
        # Strategy 2: Try exact match without subsection
        query = text("""
            SELECT statute_id FROM statutes_dim
            WHERE jurisdiction = 'WA'
            AND code = :code
            AND title = :title
            AND section = :section
            LIMIT 1
        """)
        result = conn.execute(query, {
            'code': code,
            'title': title,
            'section': section
        })
        row = result.fetchone()
        if row:
            return row.statute_id
        
        # Strategy 3: Try partial section match (section starts with our section)
        query = text("""
            SELECT statute_id FROM statutes_dim
            WHERE jurisdiction = 'WA'
            AND code = :code
            AND title = :title
            AND section LIKE :section_pattern
            LIMIT 1
        """)
        result = conn.execute(query, {
            'code': code,
            'title': title,
            'section_pattern': f"{section}%"
        })
        row = result.fetchone()
        if row:
            return row.statute_id
        
        # Strategy 4: Create new statute entry if not found
        display_text = f"{code} {title}.{section}"
        if subsection:
            display_text += subsection  # subsection already includes parentheses, e.g., "(1)(a)"
        
        insert_query = text("""
            INSERT INTO statutes_dim (
                jurisdiction, code, title, section, subsection, display_text
            ) VALUES (
                'WA', :code, :title, :section, :subsection, :display_text
            )
            ON CONFLICT (jurisdiction, code, title, section, COALESCE(subsection, '')) DO UPDATE
            SET display_text = EXCLUDED.display_text
            RETURNING statute_id
        """)
        
        result = conn.execute(insert_query, {
            'code': code,
            'title': title,
            'section': section,
            'subsection': subsection,
            'display_text': display_text
        })
        
        row = result.fetchone()
        if row:
            logger.info(f"Created new statute in statutes_dim: {display_text} (ID: {row.statute_id})")
            return row.statute_id
        
        return None
    
    def _insert_statute(self, conn, case_id: int, statute: Statute) -> int:
        """Insert a statute citation with statute_id resolution."""
        # Try to resolve statute_id
        statute_id = self._resolve_statute_id(conn, statute.citation)
        
        query = text("""
            INSERT INTO statute_citations (case_id, statute_id, raw_text, created_at)
            VALUES (:case_id, :statute_id, :raw_text, :created_at)
            RETURNING id
        """)
        
        result = conn.execute(query, {
            'case_id': case_id,
            'statute_id': statute_id,
            'raw_text': statute.citation,
            'created_at': datetime.now(),
        })
        
        return result.fetchone().id
    
    def _resolve_rcw_reference(self, conn, rcw_references: Optional[List[str]]) -> Optional[str]:
        """
        Resolve RCW references to a single rcw_reference string for issues_decisions.
        Also attempts to link to statutes_dim for the first RCW.
        
        Args:
            conn: Database connection
            rcw_references: List of RCW citations (e.g., ['RCW 9.94A.525', 'RCW 9.94A.530'])
            
        Returns:
            Comma-separated string of RCW references, or None
        """
        if not rcw_references:
            return None
        
        # Return first RCW as the primary reference (the column is single-valued)
        # Could also join them: ', '.join(rcw_references)
        return rcw_references[0] if rcw_references else None
    
    # Category normalization mapping - maps variations to canonical names
    CATEGORY_NORMALIZATION = {
        # Tort variations
        'tort': 'Tort Law',
        'tort law': 'Tort Law',
        'torts': 'Tort Law',
        # Criminal variations
        'criminal': 'Criminal Law',
        'criminal law': 'Criminal Law',
        # Civil variations
        'civil': 'Civil Procedure',
        'civil law': 'Civil Procedure',
        'civil procedure': 'Civil Procedure',
        # Constitutional variations
        'constitutional': 'Constitutional Law',
        'constitutional law': 'Constitutional Law',
        # Administrative variations
        'administrative': 'Administrative Law',
        'administrative law': 'Administrative Law',
        'admin law': 'Administrative Law',
        # Family variations
        'family': 'Family Law',
        'family law': 'Family Law',
        'domestic': 'Family Law',
        'domestic relations': 'Family Law',
        # Property variations
        'property': 'Property Law',
        'property law': 'Property Law',
        'real property': 'Property Law',
        'real estate': 'Property Law',
        # Contract variations
        'contract': 'Contract Law',
        'contract law': 'Contract Law',
        'contracts': 'Contract Law',
        # Employment variations
        'employment': 'Employment Law',
        'employment law': 'Employment Law',
        'labor': 'Employment Law',
        'labor law': 'Employment Law',
        # Evidence variations
        'evidence': 'Evidence',
        'evidentiary': 'Evidence',
    }
    
    def _normalize_category(self, category: str) -> str:
        """Normalize category name to canonical form."""
        if not category:
            return category
        lookup = category.strip().lower()
        return self.CATEGORY_NORMALIZATION.get(lookup, category.strip())
    
    def _resolve_taxonomy_id(self, conn, category: Optional[str], subcategory: Optional[str]) -> Optional[int]:
        """
        Resolve category/subcategory to taxonomy_id from legal_taxonomy table.
        Creates new taxonomy entries if they don't exist (upsert behavior).
        Normalizes category names to canonical forms.
        
        Args:
            conn: Database connection
            category: Issue category (e.g., 'Criminal Law')
            subcategory: Issue subcategory (e.g., 'Jury Selection and Batson Challenges')
            
        Returns:
            taxonomy_id for the subcategory (or category if no subcategory), or None
        """
        if not category:
            return None
        
        # Normalize category to canonical form
        category = self._normalize_category(category)
        if not category:
            return None
        
        # Step 1: Get or create the category entry
        # Use COALESCE(-1) to match the unique index on (COALESCE(parent_id, -1), name, level_type)
        cat_query = text("""
            INSERT INTO legal_taxonomy (parent_id, name, level_type)
            VALUES (NULL, :name, 'category')
            ON CONFLICT (COALESCE(parent_id, -1), name, level_type) DO NOTHING
            RETURNING taxonomy_id
        """)
        cat_result = conn.execute(cat_query, {'name': category})
        row = cat_result.fetchone()
        
        if row:
            category_id = row.taxonomy_id
        else:
            # Entry already exists, fetch it
            fetch_cat = text("""
                SELECT taxonomy_id FROM legal_taxonomy 
                WHERE parent_id IS NULL AND name = :name AND level_type = 'category'
            """)
            category_id = conn.execute(fetch_cat, {'name': category}).fetchone().taxonomy_id
        
        # If no subcategory, return the category_id
        if not subcategory:
            return category_id
        
        subcategory = subcategory.strip()
        if not subcategory:
            return category_id
        
        # Step 2: Get or create the subcategory entry linked to the category
        subcat_query = text("""
            INSERT INTO legal_taxonomy (parent_id, name, level_type)
            VALUES (:parent_id, :name, 'subcategory')
            ON CONFLICT (COALESCE(parent_id, -1), name, level_type) DO NOTHING
            RETURNING taxonomy_id
        """)
        subcat_result = conn.execute(subcat_query, {'parent_id': category_id, 'name': subcategory})
        row = subcat_result.fetchone()
        
        if row:
            return row.taxonomy_id
        else:
            # Entry already exists, fetch it
            fetch_subcat = text("""
                SELECT taxonomy_id FROM legal_taxonomy 
                WHERE parent_id = :parent_id AND name = :name AND level_type = 'subcategory'
            """)
            return conn.execute(fetch_subcat, {'parent_id': category_id, 'name': subcategory}).fetchone().taxonomy_id

    def _insert_issue(self, conn, case_id: int, issue: Issue) -> int:
        """
        Insert an issue/decision record with full field population.
        Links RCW references from the issue to statutes_dim.
        Links to legal_taxonomy via taxonomy_id.
        """
        # Resolve RCW reference (use first one as primary)
        rcw_reference = self._resolve_rcw_reference(conn, issue.rcw_references)
        
        # Resolve taxonomy_id from category/subcategory
        taxonomy_id = self._resolve_taxonomy_id(conn, issue.category, issue.subcategory)
        
        query = text("""
            INSERT INTO issues_decisions (
                case_id, issue_summary, rcw_reference, keywords, 
                decision_stage, decision_summary, appeal_outcome, 
                winner_legal_role, winner_personal_role,
                confidence_score, taxonomy_id, created_at, updated_at
            ) VALUES (
                :case_id, :issue_summary, :rcw_reference, :keywords,
                :decision_stage, :decision_summary, :appeal_outcome,
                :winner_legal_role, :winner_personal_role,
                :confidence_score, :taxonomy_id, :created_at, :updated_at
            )
            RETURNING issue_id
        """)
        
        now = datetime.now()
        
        result = conn.execute(query, {
            'case_id': case_id,
            'issue_summary': issue.summary,
            'rcw_reference': rcw_reference,
            'keywords': issue.keywords,  # PostgreSQL array
            'decision_stage': issue.decision_stage or 'appeal',
            'decision_summary': issue.decision_summary,
            'appeal_outcome': issue.outcome,
            'winner_legal_role': issue.winner,
            'winner_personal_role': issue.winner_personal_role,
            'confidence_score': issue.confidence_score,
            'taxonomy_id': taxonomy_id,
            'created_at': now,
            'updated_at': now,
        })
        
        return result.fetchone().issue_id
    
    def _insert_argument(self, conn, case_id: int, issue_id: int, side: str, argument_text: str) -> int:
        """
        Insert a legal argument record for an issue.
        
        Args:
            conn: Database connection
            case_id: The case ID
            issue_id: The issue ID this argument relates to
            side: 'appellant' or 'respondent'
            argument_text: The text of the argument
            
        Returns:
            The argument_id of the inserted row
        """
        query = text("""
            INSERT INTO arguments (case_id, issue_id, side, argument_text, created_at, updated_at)
            VALUES (:case_id, :issue_id, :side, :argument_text, :created_at, :updated_at)
            RETURNING argument_id
        """)
        
        now = datetime.now()
        
        result = conn.execute(query, {
            'case_id': case_id,
            'issue_id': issue_id,
            'side': side,
            'argument_text': argument_text,
            'created_at': now,
            'updated_at': now,
        })
        
        return result.fetchone().argument_id
    
    def insert_batch(
        self, 
        cases: List[ExtractedCase], 
        max_workers: int = 4,
        progress_callback=None
    ) -> Dict[str, int]:
        """
        Insert a batch of cases in parallel.
        
        Args:
            cases: List of ExtractedCase objects
            max_workers: Number of parallel workers for DB+RAG processing
            progress_callback: Optional callback(case, case_id, error, was_duplicate)
                              called after each case insert attempt
            
        Returns:
            Dictionary with success/failure counts
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
        
        results = {'success': 0, 'failed': 0, 'case_ids': [], 'duplicates': 0}
        
        if not cases:
            return results
        
        def process_single_case(case: ExtractedCase) -> Optional[int]:
            """Process a single case (insert + RAG)."""
            try:
                result = self.insert_case(case)
                logger.debug(f"insert_case returned {result} for {case.metadata.case_number}")
                return result
            except Exception as e:
                logger.error(f"insert_case exception for {case.metadata.case_number}: {e}")
                raise
        
        # Process cases in parallel
        logger.info(f"Processing {len(cases)} cases with {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_case = {executor.submit(process_single_case, case): case for case in cases}
            
            try:
                for future in as_completed(future_to_case, timeout=900):  # 15 minute timeout for batch
                    case = future_to_case[future]
                    try:
                        case_id = future.result(timeout=300)  # 5 minute timeout per case
                        if case_id:
                            was_duplicate = (case_id == -1)
                            if was_duplicate:  # Duplicate marker
                                results['duplicates'] += 1
                            else:
                                results['success'] += 1
                                results['case_ids'].append(case_id)
                            
                            # Call progress callback on success
                            if progress_callback:
                                try:
                                    progress_callback(case, case_id if case_id != -1 else 0, None, was_duplicate)
                                except Exception as cb_err:
                                    logger.warning(f"Progress callback error: {cb_err}")
                        else:
                            results['failed'] += 1
                            if progress_callback:
                                try:
                                    progress_callback(case, None, "Insert returned None", False)
                                except Exception as cb_err:
                                    logger.warning(f"Progress callback error: {cb_err}")
                    except (TimeoutError, FuturesTimeoutError) as te:
                        logger.error(f"Case processing timed out for {case.metadata.case_number}: {te}")
                        results['failed'] += 1
                        if progress_callback:
                            try:
                                progress_callback(case, None, "Timeout", False)
                            except Exception as cb_err:
                                logger.warning(f"Progress callback error: {cb_err}")
                    except Exception as e:
                        logger.error(f"Case processing error for {case.metadata.case_number}: {e}")
                        results['failed'] += 1
                        if progress_callback:
                            try:
                                progress_callback(case, None, str(e), False)
                            except Exception as cb_err:
                                logger.warning(f"Progress callback error: {cb_err}")
            except (TimeoutError, FuturesTimeoutError) as te:
                logger.error(f"Batch processing timed out: {te}")
                # Mark remaining cases as failed
                for f, c in future_to_case.items():
                    if not f.done():
                        results['failed'] += 1
                        if progress_callback:
                            try:
                                progress_callback(c, None, "Batch timeout", False)
                            except:
                                pass
        
        # Ensure all threads are done before returning
        logger.debug("Waiting for executor shutdown...")
        # ThreadPoolExecutor's context manager already waits for all futures, but log it
        
        logger.info(
            f"Batch insert complete: {results['success']} success, "
            f"{results['duplicates']} duplicates updated, {results['failed']} failed"
        )
        
        # Force flush logs
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        
        return results
    
    def get_case_count(self) -> int:
        """Get total number of cases in database."""
        with self.db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM cases"))
            return result.scalar()
