from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CitationEdgeBase(BaseModel):
    source_case_id: int = Field(..., description="Source case ID")
    target_case_citation: str = Field(..., description="Target case citation text")
    target_case_id: Optional[int] = Field(None, description="Resolved target case ID")
    relationship: Optional[str] = Field(None, description="Citation relationship (cites, distinguishes, overrules)")
    importance: Optional[str] = Field(None, description="Citation importance (key, support)")
    pin_cite: Optional[str] = Field(None, description="Pin cite reference")


class CitationEdgeCreate(BaseModel):
    source_case_id: int
    target_case_citation: str
    target_case_id: Optional[int] = None
    relationship: Optional[str] = None
    importance: Optional[str] = None
    pin_cite: Optional[str] = None


class CitationEdgeUpdate(BaseModel):
    target_case_id: Optional[int] = None
    relationship: Optional[str] = None
    importance: Optional[str] = None
    pin_cite: Optional[str] = None


class CitationEdge(CitationEdgeBase):
    citation_id: int = Field(..., description="Unique citation identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class CitationEdgeResponse(CitationEdge):
    pass
