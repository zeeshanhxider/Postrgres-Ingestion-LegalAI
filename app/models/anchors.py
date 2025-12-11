from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class IssueChunkBase(BaseModel):
    issue_id: int = Field(..., description="Associated issue ID")
    case_id: int = Field(..., description="Associated case ID")
    chunk_id: int = Field(..., description="Associated chunk ID")
    evidence_score: Optional[float] = Field(None, description="Evidence confidence score", ge=0.0, le=1.0)


class IssueChunkCreate(IssueChunkBase):
    pass


class IssueChunk(IssueChunkBase):
    id: int = Field(..., description="Unique issue-chunk link identifier")

    class Config:
        from_attributes = True


