"""
Dimension Table Service
Handles lookups and creation of dimension table records (case_types, stage_types, document_types, courts).
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

class DimensionService:
    """Service for managing dimension table lookups and creation"""
    
    def __init__(self, db_engine: Engine):
        self.db = db_engine
        self._cache = {
            'case_types': {},
            'stage_types': {},
            'document_types': {},
            'courts': {}
        }
    
    def get_or_create_case_type(self, case_type: str, description: str = None, jurisdiction: str = "WA") -> int:
        """Get or create case type and return ID"""
        # Check cache first
        cache_key = f"{case_type}_{jurisdiction}"
        if cache_key in self._cache['case_types']:
            return self._cache['case_types'][cache_key]
        
        with self.db.connect() as conn:
            # Try to find existing
            query = text("SELECT case_type_id FROM case_types WHERE case_type = :case_type AND jurisdiction = :jurisdiction")
            result = conn.execute(query, {'case_type': case_type, 'jurisdiction': jurisdiction})
            row = result.fetchone()
            
            if row:
                case_type_id = row.case_type_id
                logger.debug(f"Found existing case type: {case_type} -> ID {case_type_id}")
            else:
                # Create new
                insert_query = text("""
                    INSERT INTO case_types (case_type, description, jurisdiction, created_at)
                    VALUES (:case_type, :description, :jurisdiction, NOW())
                    RETURNING case_type_id
                """)
                result = conn.execute(insert_query, {
                    'case_type': case_type,
                    'description': description or f"{case_type} case type",
                    'jurisdiction': jurisdiction
                })
                case_type_id = result.fetchone().case_type_id
                conn.commit()
                logger.info(f"Created new case type: {case_type} -> ID {case_type_id}")
            
            # Cache result
            self._cache['case_types'][cache_key] = case_type_id
            return case_type_id
    
    def get_or_create_stage_type(self, stage_type: str, description: str = None, level: int = 1) -> int:
        """Get or create stage type and return ID"""
        # Check cache first
        if stage_type in self._cache['stage_types']:
            return self._cache['stage_types'][stage_type]
        
        with self.db.connect() as conn:
            # Try to find existing
            query = text("SELECT stage_type_id FROM stage_types WHERE stage_type = :stage_type")
            result = conn.execute(query, {'stage_type': stage_type})
            row = result.fetchone()
            
            if row:
                stage_type_id = row.stage_type_id
                logger.debug(f"Found existing stage type: {stage_type} -> ID {stage_type_id}")
            else:
                # Create new
                insert_query = text("""
                    INSERT INTO stage_types (stage_type, description, level, created_at)
                    VALUES (:stage_type, :description, :level, NOW())
                    RETURNING stage_type_id
                """)
                result = conn.execute(insert_query, {
                    'stage_type': stage_type,
                    'description': description or f"{stage_type} legal stage",
                    'level': level
                })
                stage_type_id = result.fetchone().stage_type_id
                conn.commit()
                logger.info(f"Created new stage type: {stage_type} -> ID {stage_type_id}")
            
            # Cache result
            self._cache['stage_types'][stage_type] = stage_type_id
            return stage_type_id
    
    def get_or_create_document_type(self, document_type: str, description: str = None, has_decision: bool = True) -> int:
        """Get or create document type and return ID"""
        # Check cache first
        if document_type in self._cache['document_types']:
            return self._cache['document_types'][document_type]
        
        with self.db.connect() as conn:
            # Try to find existing
            query = text("SELECT document_type_id FROM document_types WHERE document_type = :document_type")
            result = conn.execute(query, {'document_type': document_type})
            row = result.fetchone()
            
            if row:
                document_type_id = row.document_type_id
                logger.debug(f"Found existing document type: {document_type} -> ID {document_type_id}")
            else:
                # Create new
                insert_query = text("""
                    INSERT INTO document_types (document_type, description, has_decision, created_at)
                    VALUES (:document_type, :description, :has_decision, NOW())
                    RETURNING document_type_id
                """)
                result = conn.execute(insert_query, {
                    'document_type': document_type,
                    'description': description or f"{document_type} document",
                    'has_decision': has_decision
                })
                document_type_id = result.fetchone().document_type_id
                conn.commit()
                logger.info(f"Created new document type: {document_type} -> ID {document_type_id}")
            
            # Cache result
            self._cache['document_types'][document_type] = document_type_id
            return document_type_id
    
    def get_or_create_court(self, court_name: str, level: str = None, jurisdiction: str = "WA", 
                           district: str = None, county: str = None) -> int:
        """Get or create court and return ID"""
        # Check cache first
        if court_name in self._cache['courts']:
            return self._cache['courts'][court_name]
        
        with self.db.connect() as conn:
            # Try to find existing
            query = text("SELECT court_id FROM courts_dim WHERE court = :court_name")
            result = conn.execute(query, {'court_name': court_name})
            row = result.fetchone()
            
            if row:
                court_id = row.court_id
                logger.debug(f"Found existing court: {court_name} -> ID {court_id}")
            else:
                # Create new
                insert_query = text("""
                    INSERT INTO courts_dim (court, level, jurisdiction, district, county)
                    VALUES (:court, :level, :jurisdiction, :district, :county)
                    RETURNING court_id
                """)
                result = conn.execute(insert_query, {
                    'court': court_name,
                    'level': level or "Court of Appeals",
                    'jurisdiction': jurisdiction,
                    'district': district,
                    'county': county
                })
                court_id = result.fetchone().court_id
                conn.commit()
                logger.info(f"Created new court: {court_name} -> ID {court_id}")
            
            # Cache result
            self._cache['courts'][court_name] = court_id
            return court_id
    
    def resolve_metadata_to_ids(self, metadata: Dict[str, Any]) -> Dict[str, Optional[int]]:
        """Convert metadata strings to dimension table IDs"""
        try:
            # Default case type mapping
            case_type_map = {
                'divorce': 'Divorce',
                'marriage': 'Marriage Dissolution',
                'family': 'Family Law',
                'civil': 'Civil',
                'criminal': 'Criminal'
            }
            
            # Default stage type mapping  
            stage_type_map = {
                'trial': 'Trial Court',
                'appeals': 'Court of Appeals',
                'appeal': 'Court of Appeals',
                'supreme': 'Supreme Court'
            }
            
            # Default document type mapping
            doc_type_map = {
                'decision': 'Court Decision',
                'opinion': 'Court Opinion', 
                'order': 'Court Order',
                'judgment': 'Judgment'
            }
            
            # Resolve IDs
            case_type = metadata.get('case_type', 'divorce').lower()
            court_level = metadata.get('court_level', 'appeals').lower()
            court_name = metadata.get('court', 'Washington State Court of Appeals')
            
            return {
                'case_type_id': self.get_or_create_case_type(
                    case_type_map.get(case_type, case_type.title())
                ),
                'stage_type_id': self.get_or_create_stage_type(
                    stage_type_map.get(court_level, court_level.title()),
                    level=2 if 'appeal' in court_level else 1
                ),
                'document_type_id': self.get_or_create_document_type('Court Decision'),
                'court_id': self.get_or_create_court(
                    court_name,
                    level=stage_type_map.get(court_level, court_level.title())
                )
            }
            
        except Exception as e:
            logger.error(f"Error resolving metadata to IDs: {e}")
            return {
                'case_type_id': None,
                'stage_type_id': None, 
                'document_type_id': None,
                'court_id': None
            }
    
    def clear_cache(self):
        """Clear the internal cache"""
        for cache in self._cache.values():
            cache.clear()
        logger.info("Dimension service cache cleared")
