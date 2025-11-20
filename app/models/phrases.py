from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CasePhraseBase(BaseModel):
    phrase: str = Field(..., description="Phrase text")
    n: int = Field(..., description="N-gram size", ge=2, le=4)
    frequency: int = Field(..., description="Phrase frequency")
    example_sentence: Optional[int] = Field(None, description="Example sentence ID")
    example_chunk: Optional[int] = Field(None, description="Example chunk ID")


class CasePhraseCreate(BaseModel):
    case_id: int
    document_id: Optional[int] = None
    phrase: str
    n: int = Field(..., ge=2, le=4)
    frequency: int
    example_sentence: Optional[int] = None
    example_chunk: Optional[int] = None


class CasePhraseUpdate(BaseModel):
    frequency: Optional[int] = None
    example_chunk: Optional[int] = None


class CasePhrase(CasePhraseBase):
    phrase_id: int = Field(..., description="Unique phrase identifier")
    case_id: int = Field(..., description="Associated case ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class CasePhraseResponse(CasePhrase):
    pass
