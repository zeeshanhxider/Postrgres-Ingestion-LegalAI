from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CaseSentenceBase(BaseModel):
    sentence_order: int = Field(..., description="Order within chunk")
    global_sentence_order: int = Field(..., description="Order within entire case")
    text: str = Field(..., description="Sentence text content")
    word_count: int = Field(0, description="Number of words in sentence")


class CaseSentenceCreate(BaseModel):
    case_id: int = Field(..., description="Associated case ID")
    chunk_id: int = Field(..., description="Associated chunk ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    sentence_order: int = Field(..., description="Order within chunk")
    global_sentence_order: int = Field(..., description="Order within entire case")
    text: str = Field(..., description="Sentence text content")
    embedding: Optional[List[float]] = Field(None, description="Sentence embedding vector")
    word_count: int = Field(0, description="Number of words in sentence")


class CaseSentenceUpdate(BaseModel):
    sentence_order: Optional[int] = None
    global_sentence_order: Optional[int] = None
    text: Optional[str] = None
    embedding: Optional[List[float]] = None
    word_count: Optional[int] = None


class CaseSentence(CaseSentenceBase):
    sentence_id: int = Field(..., description="Unique sentence identifier")
    case_id: int = Field(..., description="Associated case ID")
    chunk_id: int = Field(..., description="Associated chunk ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    embedding: Optional[List[float]] = Field(None, description="Sentence embedding vector")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    class Config:
        from_attributes = True


class CaseSentenceResponse(CaseSentence):
    pass


# Sentence with related data
class CaseSentenceWithRelations(CaseSentence):
    case: Optional['Case'] = None
    chunk: Optional['CaseChunk'] = None
    document: Optional['Document'] = None
