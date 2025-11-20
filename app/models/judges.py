from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class JudgeBase(BaseModel):
    name: str = Field(..., description="Judge name")


class JudgeCreate(JudgeBase):
    pass


class JudgeUpdate(BaseModel):
    name: Optional[str] = None


class Judge(JudgeBase):
    judge_id: int = Field(..., description="Unique judge identifier")

    class Config:
        from_attributes = True


class JudgeResponse(Judge):
    pass


# Case Judges (many-to-many relationship)
class CaseJudgeBase(BaseModel):
    case_id: int = Field(..., description="Associated case ID")
    judge_id: int = Field(..., description="Judge identifier")
    role: Optional[str] = Field(None, description="Judge role (Author, Concurring, Dissenting, Panelist)")
    court: Optional[str] = Field(None, description="Court name")


class CaseJudgeCreate(CaseJudgeBase):
    pass


class CaseJudgeUpdate(BaseModel):
    role: Optional[str] = None
    court: Optional[str] = None


class CaseJudge(CaseJudgeBase):
    id: int = Field(..., description="Unique case-judge relationship identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class CaseJudgeResponse(CaseJudge):
    pass
