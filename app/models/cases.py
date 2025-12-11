from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID


class CaseBase(BaseModel):
    case_file_id: Optional[str] = Field(None, description="Legal case number from document (e.g., '73404-1')")
    title: str = Field(..., description="Case title")
    court_level: Optional[str] = Field(None, description="Court level")
    court: Optional[str] = Field(None, description="Court name")
    district: Optional[str] = Field(None, description="District")
    county: Optional[str] = Field(None, description="County")
    docket_number: Optional[str] = Field(None, description="Docket number")
    source_docket_number: Optional[str] = Field(None, description="Source docket number")
    trial_judge: Optional[str] = Field(None, description="Trial judge name")

    # Trial court dates
    trial_start_date: Optional[date] = Field(None, description="When the divorce case began")
    trial_end_date: Optional[date] = Field(None, description="When trial court made its decision")
    trial_published_date: Optional[date] = Field(None, description="When trial court decision was published")
    
    # Appellate court dates
    appeal_start_date: Optional[date] = Field(None, description="When someone appealed the trial decision")
    appeal_end_date: Optional[date] = Field(None, description="When appellate court made final decision")
    appeal_published_date: Optional[date] = Field(None, description="When appellate court decision was published")
    
    # Additional court dates
    oral_argument_date: Optional[date] = Field(None, description="When oral arguments were presented")
    published: Optional[bool] = Field(None, description="Whether case is published")

    summary: Optional[str] = Field(None, description="Case summary")
    full_text: Optional[str] = Field(None, description="Full case text")

    # Enhanced type classification
    case_type_id: Optional[int] = Field(None, description="References case_types.case_type_id")
    stage_type_id: Optional[int] = Field(None, description="References stage_types.stage_type_id")
    court_id: Optional[int] = Field(None, description="References courts_dim.court_id")
    parent_case_id: Optional[int] = Field(None, description="References parent case ID")
    
    # Overall case outcome
    overall_case_outcome: Optional[str] = Field(None, description="Overall case outcome")
    
    # Legacy case classification (for compatibility)
    case_type: Optional[str] = Field(default="divorce", description="Type of case (divorce, marriage, criminal, civil, family, business, etc.)")

    # Legacy winner data (for compatibility)
    winner_legal_role: Optional[str] = Field(None, description="Winner's legal role")
    winner_personal_role: Optional[str] = Field(None, description="Winner's personal role")
    appeal_outcome: Optional[str] = Field(None, description="Appeal outcome")
    
    # Source file information
    source_file: Optional[str] = Field(None, description="Original PDF filename")
    source_file_path: Optional[str] = Field(None, description="Full path to source PDF file")
    source_url: Optional[str] = Field(None, description="Original URL or link to the case")
    extraction_timestamp: Optional[datetime] = Field(None, description="When this case was extracted")


class CaseCreate(BaseModel):
    case_file_id: Optional[str] = None
    title: str
    court_level: Optional[str] = None
    court: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None
    docket_number: Optional[str] = None
    source_docket_number: Optional[str] = None
    trial_judge: Optional[str] = None

    # Trial court dates
    trial_start_date: Optional[date] = None
    trial_end_date: Optional[date] = None
    trial_published_date: Optional[date] = None
    
    # Appellate court dates
    appeal_start_date: Optional[date] = None
    appeal_end_date: Optional[date] = None
    appeal_published_date: Optional[date] = None
    
    # Additional court dates
    oral_argument_date: Optional[date] = None
    published: Optional[bool] = None

    summary: Optional[str] = None
    full_text: Optional[str] = None
    full_embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    embedding_created_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # Case classification
    case_type: Optional[str] = Field(default="divorce", description="Type of case")

    # Winner data from decisions - these fields exist in the database schema
    winner_legal_role: Optional[str] = None
    winner_personal_role: Optional[str] = None
    appeal_outcome: Optional[str] = None
    
    # Source file information for traceability
    source_file: Optional[str] = None
    source_file_path: Optional[str] = None
    extraction_timestamp: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    court_level: Optional[str] = None
    court: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None
    docket_number: Optional[str] = None
    source_docket_number: Optional[str] = None
    trial_judge: Optional[str] = None

    # Trial court dates
    trial_start_date: Optional[date] = None
    trial_end_date: Optional[date] = None
    trial_published_date: Optional[date] = None
    
    # Appellate court dates
    appeal_start_date: Optional[date] = None
    appeal_end_date: Optional[date] = None
    appeal_published_date: Optional[date] = None
    
    # Additional court dates
    oral_argument_date: Optional[date] = None
    published: Optional[bool] = None

    summary: Optional[str] = None
    full_text: Optional[str] = None

    # Case classification
    case_type: Optional[str] = None

    winner_legal_role: Optional[str] = None
    winner_personal_role: Optional[str] = None
    appeal_outcome: Optional[str] = None


class Case(CaseBase):
    case_id: int = Field(..., description="Unique case identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    class Config:
        from_attributes = True


class CaseResponse(Case):
    pass


# Response with related data
class CaseWithRelations(Case):
    # Related lookup data
    case_type_ref: Optional['CaseType'] = None
    stage_type_ref: Optional['StageType'] = None
    court_ref: Optional['Court'] = None
    parent_case: Optional['Case'] = None
    
    # Related entities
    documents: Optional[List['Document']] = []
    parties: Optional[List['Party']] = []
    attorneys: Optional[List['Attorney']] = []
    issues: Optional[List['EnhancedIssue']] = []
    judges: Optional[List['CaseJudge']] = []
    
    # Text processing data
    chunks: Optional[List['CaseChunk']] = []
    sentences: Optional[List['CaseSentence']] = []
