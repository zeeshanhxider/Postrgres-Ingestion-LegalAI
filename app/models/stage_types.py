from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StageTypeBase(BaseModel):
    stage_type: str = Field(..., description="Legal stage type name")
    description: Optional[str] = Field(None, description="Stage type description")
    level: int = Field(..., description="Stage level in legal process")


class StageTypeCreate(StageTypeBase):
    pass


class StageTypeUpdate(BaseModel):
    stage_type: Optional[str] = None
    description: Optional[str] = None
    level: Optional[int] = None


class StageType(StageTypeBase):
    stage_type_id: int = Field(..., description="Unique stage type identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class StageTypeResponse(StageType):
    pass
