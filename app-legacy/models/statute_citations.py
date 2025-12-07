from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class StatuteCitationBase(BaseModel):
    case_id: int = Field(..., description="Associated case ID")
    statute_id: Optional[int] = Field(None, description="Referenced statute ID")
    raw_text: Optional[str] = Field(None, description="Raw citation text")


class StatuteCitationCreate(StatuteCitationBase):
    pass


class StatuteCitationUpdate(BaseModel):
    statute_id: Optional[int] = None
    raw_text: Optional[str] = None


class StatuteCitation(StatuteCitationBase):
    id: int = Field(..., description="Unique statute citation identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class StatuteCitationResponse(StatuteCitation):
    pass
