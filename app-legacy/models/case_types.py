from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CaseTypeBase(BaseModel):
    case_type: str = Field(..., description="Case type name")
    description: Optional[str] = Field(None, description="Case type description")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction for this case type")


class CaseTypeCreate(CaseTypeBase):
    pass


class CaseTypeUpdate(BaseModel):
    case_type: Optional[str] = None
    description: Optional[str] = None
    jurisdiction: Optional[str] = None


class CaseType(CaseTypeBase):
    case_type_id: int = Field(..., description="Unique case type identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class CaseTypeResponse(CaseType):
    pass
