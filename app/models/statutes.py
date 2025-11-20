from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class StatuteBase(BaseModel):
    jurisdiction: str = Field(..., description="Jurisdiction (e.g., 'US', 'WA')")
    code: str = Field(..., description="Code type (e.g., 'USC', 'RCW')")
    title: str = Field(..., description="Title (e.g., '10 U.S.C.')")
    section: str = Field(..., description="Section (e.g., '§ 1408')")
    subsection: Optional[str] = Field(None, description="Subsection (e.g., '(a)(4)(A)(iii)')")
    display_text: str = Field(..., description="Full display text")


class StatuteCreate(StatuteBase):
    pass


class StatuteUpdate(BaseModel):
    jurisdiction: Optional[str] = None
    code: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    display_text: Optional[str] = None


class Statute(StatuteBase):
    statute_id: int = Field(..., description="Unique statute identifier")

    class Config:
        from_attributes = True


class StatuteResponse(Statute):
    pass
