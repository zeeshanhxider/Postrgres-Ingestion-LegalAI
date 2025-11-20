from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DocumentBase(BaseModel):
    title: Optional[str] = Field(None, description="Document title")
    source_url: Optional[str] = Field(None, description="Original source URL")
    local_path: Optional[str] = Field(None, description="Local file path")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    page_count: Optional[int] = Field(None, description="Number of pages")
    processing_status: str = Field("pending", description="Document processing status")


class DocumentCreate(BaseModel):
    case_id: int = Field(..., description="Associated case ID")
    stage_type_id: int = Field(..., description="Legal stage type ID")
    document_type_id: int = Field(..., description="Document type ID")
    title: Optional[str] = None
    source_url: Optional[str] = None
    local_path: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    processing_status: str = "pending"


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    source_url: Optional[str] = None
    local_path: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    processing_status: Optional[str] = None


class Document(DocumentBase):
    document_id: int = Field(..., description="Unique document identifier")
    case_id: int = Field(..., description="Associated case ID")
    stage_type_id: int = Field(..., description="Legal stage type ID")
    document_type_id: int = Field(..., description="Document type ID")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    class Config:
        from_attributes = True


class DocumentResponse(Document):
    pass


# Document with related data
class DocumentWithRelations(Document):
    case: Optional['Case'] = None
    stage_type: Optional['StageType'] = None
    document_type: Optional['DocumentType'] = None
