from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PartyBase(BaseModel):
    party_id: int = Field(..., description="Unique party identifier")
    case_id: int = Field(..., description="Associated case ID")
    name: str = Field(..., description="Party name")
    legal_role: Optional[str] = Field(None, description="Legal role (Appellant, Respondent, etc.)")
    personal_role: Optional[str] = Field(None, description="Personal role (Husband, Wife, etc.)")
    party_type: Optional[str] = Field(None, description="Party type (Individual, Organization)")


class PartyCreate(PartyBase):
    pass


class PartyUpdate(BaseModel):
    name: Optional[str] = None
    legal_role: Optional[str] = None
    personal_role: Optional[str] = None
    party_type: Optional[str] = None


class Party(PartyBase):
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class PartyResponse(Party):
    pass
