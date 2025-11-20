"""
Navigation API endpoints for word-to-document navigation
Enables hierarchical traversal from words to context to chunks to documents
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from app.services.context_navigator import ContextNavigator
from app.database import engine

router = APIRouter()
navigator = ContextNavigator(engine)

# Response models
class WordOccurrence(BaseModel):
    case_id: int
    chunk_id: int
    position: int
    word: str
    section: Optional[str]
    chunk_order: int
    case_title: str
    court: Optional[str]
    chunk_preview: str

class ContextWindow(BaseModel):
    target_word: str
    target_position: Optional[int]
    chunk_id: int
    context_sentence: str
    window_size: int

class ChunkData(BaseModel):
    chunk_id: int
    case_id: int
    chunk_order: int
    section: Optional[str]
    text: str
    case_title: str
    court: Optional[str]
    total_words: int

class DocumentStats(BaseModel):
    total_chunks: int
    unique_words: int
    total_words: int
    unique_phrases: int
    parties_count: int
    attorneys_count: int
    issues_count: int
    decisions_count: int

class FullDocument(BaseModel):
    case_id: int
    title: str
    court: Optional[str]
    summary: Optional[str]
    source_url: Optional[str]
    statistics: DocumentStats

# API Endpoints

@router.get("/word/{word}/occurrences", response_model=List[WordOccurrence])
async def find_word_occurrences(
    word: str,
    case_id: Optional[str] = Query(None, description="Filter by specific case"),
    limit: int = Query(20, description="Maximum results")
):
    """
    Find all occurrences of a word across cases
    
    Example: GET /word/custody/occurrences?limit=10
    """
    try:
        occurrences = navigator.find_word_in_context(word, case_id, limit)
        return occurrences
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/word/{word}/context/{chunk_id}", response_model=ContextWindow)
async def get_word_context(
    word: str,
    chunk_id: int,
    window_size: int = Query(10, description="Words before/after target")
):
    """
    Get context window around a word in a specific chunk
    
    Example: GET /word/custody/context/uuid-123?window_size=15
    """
    try:
        context = navigator.get_word_context_window(word, chunk_id, window_size)
        if not context:
            raise HTTPException(status_code=404, detail="Word not found in chunk")
        return context
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chunk/{chunk_id}", response_model=ChunkData)
async def get_chunk_data(
    chunk_id: int,
    highlight: Optional[List[str]] = Query(None, description="Words to highlight")
):
    """
    Get full chunk data with optional word highlighting
    
    Example: GET /chunk/uuid-123?highlight=custody&highlight=support
    """
    try:
        chunk_data = navigator.get_chunk_with_highlights(chunk_id, highlight)
        if not chunk_data:
            raise HTTPException(status_code=404, detail="Chunk not found")
        return chunk_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chunk/{chunk_id}/adjacent")
async def get_adjacent_chunks(
    chunk_id: int,
    before: int = Query(10, description="Chunks before target"),
    after: int = Query(10, description="Chunks after target")
):
    """
    Get chunks surrounding the target chunk
    
    Example: GET /chunk/uuid-123/adjacent?before=5&after=5
    """
    try:
        adjacent = navigator.get_adjacent_chunks(chunk_id, before, after)
        return adjacent
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chunk/{chunk_id}/document", response_model=FullDocument)
async def get_document_from_chunk(chunk_id: int):
    """
    Get complete document information from any chunk
    
    Example: GET /chunk/uuid-123/document
    """
    try:
        document = navigator.get_document_from_chunk(chunk_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/word/{word}/complete-navigation")
async def complete_word_navigation(
    word: str,
    case_id: Optional[str] = Query(None, description="Filter by specific case"),
    limit: int = Query(5, description="Maximum word occurrences")
):
    """
    Complete navigation from word to full document context
    
    This is the "master" endpoint that combines all navigation steps:
    1. Find word occurrences
    2. Get context windows
    3. Get chunk data
    4. Get adjacent chunks  
    5. Get full documents
    
    Example: GET /word/custody/complete-navigation
    """
    try:
        navigation_data = navigator.navigate_word_to_document(word, case_id)
        
        # Limit results to prevent large responses
        if len(navigation_data) > limit:
            navigation_data = navigation_data[:limit]
        
        return {
            "word": word,
            "total_occurrences": len(navigation_data),
            "navigation_results": navigation_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Utility endpoints for phrase exploration

@router.get("/phrases/similar/{phrase}")
async def find_similar_phrases(
    phrase: str,
    limit: int = Query(20, description="Maximum results")
):
    """
    Find phrases similar to the input phrase
    Uses trigram similarity for legal terminology discovery
    """
    try:
        from app.services.phrase_extractor import PhraseExtractor
        phrase_extractor = PhraseExtractor(engine)
        
        similar = phrase_extractor.find_similar_phrases(phrase, limit)
        return similar
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/phrases/top")
async def get_top_phrases(
    court: Optional[str] = Query(None, description="Filter by court"),
    limit: int = Query(50, description="Maximum results")
):
    """
    Get most frequent legal phrases across cases
    """
    try:
        from app.services.phrase_extractor import PhraseExtractor
        phrase_extractor = PhraseExtractor(engine)
        
        top_phrases = phrase_extractor.get_top_phrases(court, limit)
        return top_phrases
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Examples endpoint for API documentation
@router.get("/examples")
async def get_navigation_examples():
    """Get API usage examples and workflow information"""
    return {
        "description": "Word-to-Document Navigation API",
        "examples": {
            "basic_word_search": {
                "url": "/word/custody/occurrences",
                "description": "Find all mentions of 'custody' across cases"
            },
            "word_with_context": {
                "url": "/word/custody/context/{chunk_id}?window_size=15",
                "description": "See 15 words before/after 'custody' in specific chunk"
            },
            "chunk_exploration": {
                "url": "/chunk/{chunk_id}/adjacent?before=5&after=5",
                "description": "Read 5 chunks before/after target chunk for broader context"
            },
            "document_overview": {
                "url": "/chunk/{chunk_id}/document",
                "description": "Get complete case information from any chunk"
            },
            "complete_workflow": {
                "url": "/word/custody/complete-navigation",
                "description": "Full word-to-document navigation in one call"
            }
        },
        "workflow": [
            "1. Search for word occurrences across all cases",
            "2. Examine context around specific word occurrences", 
            "3. Read full chunks containing the target word",
            "4. Explore adjacent chunks for broader context",
            "5. Access complete case documents with statistics",
            "6. Discover related legal phrases and terminology"
        ]
    }
