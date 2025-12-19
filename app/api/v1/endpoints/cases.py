"""
Cases API endpoints for basic case management
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import text
import logging

from app.database import engine

router = APIRouter()
logger = logging.getLogger(__name__)

# Response models
class CaseResponse(BaseModel):
    case_id: int
    title: str
    court: Optional[str]
    court_level: Optional[str]
    filing_date: Optional[str]
    summary: Optional[str]
    source_url: Optional[str]

class CaseDetailResponse(CaseResponse):
    full_text: Optional[str]
    parties_count: int
    attorneys_count: int
    issues_count: int
    decisions_count: int
    chunks_count: int

@router.get("/", response_model=List[CaseResponse])
async def list_cases(
    limit: int = 20,
    offset: int = 0,
    court: Optional[str] = None
):
    """
    List all cases with basic information
    """
    try:
        with engine.connect() as conn:
            base_query = """
                SELECT 
                    case_id, title, court, court_level, filing_date, summary, source_url
                FROM cases
            """
            
            params = {}
            if court:
                base_query += " WHERE court ILIKE :court"
                params['court'] = f'%{court}%'
            
            base_query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            params.update({'limit': limit, 'offset': offset})
            
            result = conn.execute(text(base_query), params)
            
            cases = []
            for row in result:
                cases.append(CaseResponse(
                    case_id=row.case_id,
                    title=row.title,
                    court=row.court,
                    court_level=row.court_level,
                    filing_date=str(row.filing_date) if row.filing_date else None,
                    summary=row.summary,
                    source_url=row.source_url
                ))
            
            return cases
            
    except Exception as e:
        logger.error(f"Error listing cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}", response_model=CaseDetailResponse)
async def get_case(case_id: int):
    """
    Get detailed information about a specific case
    """
    try:
        with engine.connect() as conn:
            # Get case data with counts
            query = text("""
                SELECT 
                    c.case_id, c.title, c.court, c.court_level, c.filing_date, 
                    c.summary, c.source_url, c.full_text,
                    COUNT(DISTINCT p.party_id) as parties_count,
                    COUNT(DISTINCT a.attorney_id) as attorneys_count,
                    COUNT(DISTINCT i.issue_id) as issues_count,
                    COUNT(DISTINCT d.decision_id) as decisions_count,
                    COUNT(DISTINCT cc.chunk_id) as chunks_count
                FROM cases c
                LEFT JOIN parties p ON c.case_id = p.case_id
                LEFT JOIN attorneys a ON c.case_id = a.case_id
                LEFT JOIN issues i ON c.case_id = i.case_id
                LEFT JOIN decisions d ON c.case_id = d.case_id
                LEFT JOIN case_chunks cc ON c.case_id = cc.case_id
                WHERE c.case_id = :case_id
                GROUP BY c.case_id, c.title, c.court, c.court_level, c.filing_date, 
                         c.summary, c.source_url, c.full_text
            """)
            
            result = conn.execute(query, {'case_id': case_id})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            return CaseDetailResponse(
                case_id=row.case_id,
                title=row.title,
                court=row.court,
                court_level=row.court_level,
                filing_date=str(row.filing_date) if row.filing_date else None,
                summary=row.summary,
                source_url=row.source_url,
                full_text=row.full_text,
                parties_count=row.parties_count,
                attorneys_count=row.attorneys_count,
                issues_count=row.issues_count,
                decisions_count=row.decisions_count,
                chunks_count=row.chunks_count
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}/parties")
async def get_case_parties(case_id: int):
    """
    Get all parties for a specific case
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT party_id, name, legal_role, personal_role, party_type
                FROM parties
                WHERE case_id = :case_id
                ORDER BY created_at
            """)
            
            result = conn.execute(query, {'case_id': case_id})
            
            parties = []
            for row in result:
                parties.append({
                    'party_id': row.party_id,
                    'name': row.name,
                    'legal_role': row.legal_role,
                    'personal_role': row.personal_role,
                    'party_type': row.party_type
                })
            
            return parties
            
    except Exception as e:
        logger.error(f"Error getting parties for case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}/issues")
async def get_case_issues(case_id: int):
    """
    Get all issues for a specific case with Washington State categorization
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT issue_id, category, subcategory, rcw_reference, keywords, 
                       description, argument_summary
                FROM issues
                WHERE case_id = :case_id
                ORDER BY created_at
            """)
            
            result = conn.execute(query, {'case_id': case_id})
            
            issues = []
            for row in result:
                issues.append({
                    'issue_id': row.issue_id,
                    'category': row.category,
                    'subcategory': row.subcategory,
                    'rcw_reference': row.rcw_reference,
                    'keywords': row.keywords,
                    'description': row.description,
                    'argument_summary': row.argument_summary
                })
            
            return issues
            
    except Exception as e:
        logger.error(f"Error getting issues for case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}/decisions")
async def get_case_decisions(case_id: int):
    """
    Get all decisions for a specific case
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT issue_id, decision_stage, winner_legal_role, 
                       winner_personal_role, decision_summary, issue_outcome, issue_summary
                FROM issues_decisions
                WHERE case_id = :case_id
                ORDER BY created_at
            """)
            
            result = conn.execute(query, {'case_id': case_id})
            
            decisions = []
            for row in result:
                decisions.append({
                    'issue_id': row.issue_id,
                    'decision_stage': row.decision_stage,
                    'winner_legal_role': row.winner_legal_role,
                    'winner_personal_role': row.winner_personal_role,
                    'decision_summary': row.decision_summary,
                    'appeal_outcome': row.appeal_outcome,
                    'issue_summary': row.issue_summary
                })
            
            return decisions
            
    except Exception as e:
        logger.error(f"Error getting decisions for case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}/chunks")
async def get_case_chunks(case_id: int, limit: int = 20, offset: int = 0):
    """
    Get text chunks for a specific case
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT chunk_id, chunk_order, section, 
                       substring(text from 1 for 300) as preview
                FROM case_chunks
                WHERE case_id = :case_id
                ORDER BY chunk_order
                LIMIT :limit OFFSET :offset
            """)
            
            result = conn.execute(query, {
                'case_id': case_id,
                'limit': limit,
                'offset': offset
            })
            
            chunks = []
            for row in result:
                chunks.append({
                    'chunk_id': str(row.chunk_id),
                    'chunk_order': row.chunk_order,
                    'section': row.section,
                    'preview': row.preview
                })
            
            return chunks
            
    except Exception as e:
        logger.error(f"Error getting chunks for case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/overview")
async def get_system_stats():
    """
    Get overall system statistics
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    (SELECT COUNT(*) FROM cases) as total_cases,
                    (SELECT COUNT(*) FROM case_chunks) as total_chunks,
                    (SELECT COUNT(*) FROM parties) as total_parties,
                    (SELECT COUNT(*) FROM attorneys) as total_attorneys,
                    (SELECT COUNT(*) FROM issues) as total_issues,
                    (SELECT COUNT(*) FROM issues_decisions) as total_decisions,
                    (SELECT COUNT(*) FROM word_dictionary) as unique_words,
                    (SELECT COUNT(*) FROM case_phrases) as unique_phrases
            """)
            
            result = conn.execute(query)
            row = result.fetchone()
        
        return {
                'total_cases': row.total_cases,
                'total_chunks': row.total_chunks,
                'total_parties': row.total_parties,
                'total_attorneys': row.total_attorneys,
                'total_issues': row.total_issues,
                'total_decisions': row.total_decisions,
                'unique_words': row.unique_words,
                'unique_phrases': row.unique_phrases
        }
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))