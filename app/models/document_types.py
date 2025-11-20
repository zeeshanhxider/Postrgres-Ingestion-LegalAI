from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DocumentTypeBase(BaseModel):
    document_type: str = Field(..., description="Document type name")
    description: Optional[str] = Field(None, description="Document type description")
    has_decision: bool = Field(False, description="Whether this document type contains decisions")


class DocumentTypeCreate(DocumentTypeBase):
    pass


class DocumentTypeUpdate(BaseModel):
    document_type: Optional[str] = None
    description: Optional[str] = None
    has_decision: Optional[bool] = None


class DocumentType(DocumentTypeBase):
    document_type_id: int = Field(..., description="Unique document type identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True


class DocumentTypeResponse(DocumentType):
    pass
