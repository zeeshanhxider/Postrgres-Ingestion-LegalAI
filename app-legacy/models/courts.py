from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CourtBase(BaseModel):
    name: str = Field(..., description="Court name")
    level: Optional[str] = Field(None, description="Court level (e.g., 'Supreme Court', 'Court of Appeals')")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction (e.g., 'WA', 'US')")
    district: Optional[str] = Field(None, description="District name")
    county: Optional[str] = Field(None, description="County name")


class CourtCreate(CourtBase):
    pass


class CourtUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[str] = None
    jurisdiction: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None


class Court(CourtBase):
    court_id: int = Field(..., description="Unique court identifier")

    class Config:
        from_attributes = True


class CourtResponse(Court):
    pass
