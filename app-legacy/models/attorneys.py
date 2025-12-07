from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AttorneyBase(BaseModel):
    attorney_id: int = Field(..., description="Unique attorney identifier")
    case_id: int = Field(..., description="Associated case ID")
    name: str = Field(..., description="Attorney name")
    firm_name: Optional[str] = Field(None, description="Law firm name")
    firm_address: Optional[str] = Field(None, description="Firm address")
    representing: Optional[str] = Field(None, description="Party represented")
    attorney_type: Optional[str] = Field(None, description="Attorney type (Appellant Counsel, etc.)")


class AttorneyCreate(AttorneyBase):
    pass


class AttorneyUpdate(BaseModel):
    name: Optional[str] = None
    firm_name: Optional[str] = None
    firm_address: Optional[str] = None
    representing: Optional[str] = None
    attorney_type: Optional[str] = None


class Attorney(AttorneyBase):
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class AttorneyResponse(Attorney):
    pass
