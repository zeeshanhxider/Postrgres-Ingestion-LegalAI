from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CaseChunkBase(BaseModel):
    chunk_order: int = Field(..., description="Chunk order within case")
    section: Optional[str] = Field(None, description="Document section")
    text: str = Field(..., description="Chunk text content")
    sentence_count: int = Field(0, description="Number of sentences in chunk")


class CaseChunkCreate(BaseModel):
    case_id: int = Field(..., description="Associated case ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    chunk_order: int = Field(..., description="Chunk order within case")
    section: Optional[str] = Field(None, description="Document section")
    text: str = Field(..., description="Chunk text content")
    sentence_count: int = Field(0, description="Number of sentences in chunk")


class CaseChunkUpdate(BaseModel):
    section: Optional[str] = None
    text: Optional[str] = None


class CaseChunk(CaseChunkBase):
    chunk_id: int = Field(..., description="Unique chunk identifier")
    case_id: int = Field(..., description="Associated case ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    class Config:
        from_attributes = True


class CaseChunkResponse(CaseChunk):
    pass


# For OCR processing results
class OCRChunkResult(BaseModel):
    chunk_id: int
    text: str
    confidence: Optional[float] = None
    bounding_box: Optional[dict] = None
    page_number: Optional[int] = None
