from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class EnhancedIssueBase(BaseModel):
    # AI-generated legal analysis
    category: str = Field(..., description="Top-level legal category")
    subcategory: str = Field(..., description="Mid-level subcategory")
    rcw_reference: Optional[str] = Field(None, description="Washington RCW statutes reference")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Common keywords")
    issue_summary: str = Field(..., description="Specific issue description from case")
    
    # Decision details
    decision_stage: Optional[str] = Field(None, description="trial or appeal")
    decision_summary: Optional[str] = Field(None, description="What the court decided on this issue")
    appeal_outcome: Optional[str] = Field(None, description="reversed, affirmed, remanded, dismissed, partial")
    winner_legal_role: Optional[str] = Field(None, description="appellant, respondent, etc.")
    winner_personal_role: Optional[str] = Field(None, description="husband, wife, etc.")
    
    # AI metadata
    confidence_score: Optional[float] = Field(None, description="AI confidence score")


class EnhancedIssueCreate(BaseModel):
    case_id: int = Field(..., description="Associated case ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    document_type_id: Optional[int] = Field(None, description="Document type ID")
    
    # AI-generated legal analysis
    category: str = Field(..., description="Top-level legal category")
    subcategory: str = Field(..., description="Mid-level subcategory")
    rcw_reference: Optional[str] = None
    keywords: Optional[List[str]] = None
    issue_summary: str = Field(..., description="Specific issue description from case")
    
    # Decision details
    decision_stage: Optional[str] = None
    decision_summary: Optional[str] = None
    appeal_outcome: Optional[str] = None
    winner_legal_role: Optional[str] = None
    winner_personal_role: Optional[str] = None
    
    # AI metadata
    confidence_score: Optional[float] = None


class EnhancedIssueUpdate(BaseModel):
    issue_type: Optional[str] = None
    argument_subtype: Optional[str] = None
    description: Optional[str] = None
    argument_summary: Optional[str] = None

    category: Optional[str] = None
    subcategory: Optional[str] = None
    rcw_reference: Optional[str] = None
    keywords: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    classification_json: Optional[Dict[str, Any]] = None


class EnhancedIssue(EnhancedIssueBase):
    issue_id: int = Field(..., description="Unique issue identifier")
    case_id: int = Field(..., description="Associated case ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    document_type_id: Optional[int] = Field(None, description="Document type ID")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    class Config:
        from_attributes = True


class EnhancedIssueResponse(EnhancedIssue):
    pass
