"""
Excel upload endpoint for batch processing legal cases.
Integrates with the enhanced AI extraction service.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, ValidationError
from typing import Optional, Dict, Any, List
import json
import logging
import pandas as pd
from io import BytesIO
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.services.enhanced_ingest import ingest_excel_with_ai, EnhancedIngestionError

router = APIRouter()
logger = logging.getLogger(__name__)

class ExcelProcessingOptions(BaseModel):
    enable_ai_extraction: bool = True
    process_all_sheets: bool = True
    max_cases: Optional[int] = None
    start_from_row: int = 0

class BatchProcessingResponse(BaseModel):
    total_cases: int
    successful_cases: int
    failed_cases: int
    case_ids: List[str]
    processing_time_seconds: float
    stats: Dict[str, Any]

@router.post("/upload-excel", response_model=BatchProcessingResponse)
async def upload_excel_batch(
    background_tasks: BackgroundTasks,
    excel_file: UploadFile = File(...),
    processing_options: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload Excel file and process each row as a legal case with AI extraction.
    
    Uses your template pattern for:
    1. Reading Excel data (multiple sheets supported)
    2. AI extraction of legal entities
    3. Text chunking and word indexing
    4. Database storage with search capabilities
    """
    
    # Validate file type
    if not excel_file.content_type in [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel"
    ]:
        raise HTTPException(
            status_code=400, 
            detail="File must be an Excel document (.xlsx or .xls)"
        )
    
    # Parse processing options
    try:
        options_dict = json.loads(processing_options)
        options = ExcelProcessingOptions(**options_dict)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid processing options: {str(e)}"
        )
    
    # Read Excel file
    try:
        excel_content = await excel_file.read()
        if len(excel_content) == 0:
            raise HTTPException(status_code=400, detail="Empty Excel file")
        
        excel_buffer = BytesIO(excel_content)
        
        if options.process_all_sheets:
            # Read all sheets (your template pattern)
            all_sheets = pd.read_excel(excel_buffer, sheet_name=None)
            logger.info(f"Found {len(all_sheets)} sheets: {list(all_sheets.keys())}")
            
            # Combine all sheets with source tracking
            all_cases = []
            for sheet_name, df in all_sheets.items():
                df['source_sheet'] = sheet_name
                df['sheet_row_index'] = df.index
                all_cases.append(df)
            
            combined_df = pd.concat(all_cases, ignore_index=True)
        else:
            # Read first sheet only
            combined_df = pd.read_excel(excel_buffer)
            combined_df['source_sheet'] = 'default'
            combined_df['sheet_row_index'] = combined_df.index
        
        # Apply filters
        if options.start_from_row > 0:
            combined_df = combined_df.iloc[options.start_from_row:]
        
        if options.max_cases:
            combined_df = combined_df.head(options.max_cases)
        
        logger.info(f"Will process {len(combined_df)} cases from Excel")
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")
    
    # Process cases with AI extraction and chunking
    start_time = time.time()
    successful_cases = []
    failed_cases = []
    all_stats = []
    
    try:
        for index, row in combined_df.iterrows():
            try:
                logger.info(f"Processing Excel case {index + 1}/{len(combined_df)}")
                
                # Build comprehensive case text (your template pattern)
                excel_data = _build_excel_case_data(row, index)
                
                # Process with enhanced AI extraction + chunking + word indexing
                result = await ingest_excel_with_ai(
                    excel_data=excel_data,
                    enable_ai=options.enable_ai_extraction
                )
                
                successful_cases.append(result["case_id"])
                all_stats.append(result.get("stats", {}))
                
                logger.info(f"Excel case {index + 1} processed: {result['case_id']}")
                
                # Small delay to prevent overwhelming the system
                if options.enable_ai_extraction:
                    time.sleep(0.5)  # Rate limiting for AI calls
                
            except EnhancedIngestionError as e:
                error_msg = f"Row {index + 1}: {str(e)}"
                failed_cases.append(error_msg)
                logger.error(f"Failed to process Excel case {index + 1}: {str(e)}")
                continue
            except Exception as e:
                error_msg = f"Row {index + 1}: Unexpected error - {str(e)}"
                failed_cases.append(error_msg)
                logger.error(f"Unexpected error processing Excel case {index + 1}: {str(e)}")
                continue
        
        processing_time = time.time() - start_time
        
        # Aggregate statistics
        aggregated_stats = _aggregate_processing_stats(all_stats, processing_time, successful_cases)
        
        logger.info(f"Excel batch processing completed: {len(successful_cases)} successful, {len(failed_cases)} failed")
        
        return BatchProcessingResponse(
            total_cases=len(combined_df),
            successful_cases=len(successful_cases),
            failed_cases=len(failed_cases),
            case_ids=successful_cases,
            processing_time_seconds=processing_time,
            stats=aggregated_stats
        )
        
    except Exception as e:
        logger.error(f"Excel batch processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Excel processing failed: {str(e)}")

def _build_excel_case_data(row: pd.Series, index: int) -> Dict[str, Any]:
    """
    Build comprehensive case data from Excel row (template pattern).
    
    Args:
        row: Pandas Series containing Excel row data
        index: Row index
        
    Returns:
        Dictionary with case data for AI processing
    """
    excel_data = {
        "row_index": index,
        "source_sheet": row.get('source_sheet', 'Unknown'),
        "sheet_row_index": row.get('sheet_row_index', index)
    }
    
    # Add all Excel columns
    for col_idx, (col_name, col_value) in enumerate(row.items()):
        if col_name not in ['source_sheet', 'sheet_row_index']:
            excel_data[f"col_{col_idx}"] = str(col_value) if pd.notna(col_value) else ""
    
    # Add derived fields for easier processing
    excel_data.update({
        "case_title": excel_data.get("col_1", f"Excel Case {index + 1}"),
        "court": excel_data.get("col_2", "Unknown Court"),
        "docket_number": excel_data.get("col_0", f"EXCEL-{index + 1}"),
        "case_content": excel_data.get("col_8", ""),  # Main case content
        "abstract": excel_data.get("col_9", "")       # Additional content
    })
    
    return excel_data

def _aggregate_processing_stats(all_stats: List[Dict], processing_time: float, successful_cases: List[str]) -> Dict[str, Any]:
    """Aggregate statistics from all processed cases"""
    if not all_stats:
        return {
            "processing_time": processing_time,
            "success_rate": 0.0,
            "ai_extraction_rate": 0.0
        }
    
    return {
        "total_chunks": sum(s.get("chunks", 0) for s in all_stats),
        "total_words": sum(s.get("total_words", 0) for s in all_stats),
        "total_unique_words": sum(s.get("unique_words", 0) for s in all_stats),
        "total_word_occurrences": sum(s.get("word_occurrences", 0) for s in all_stats),
        "ai_extractions_successful": sum(1 for s in all_stats if s.get("ai_extracted_parties", 0) > 0),
        "ai_extraction_rate": sum(1 for s in all_stats if s.get("ai_extracted_parties", 0) > 0) / len(all_stats) * 100,
        "avg_chunks_per_case": sum(s.get("chunks", 0) for s in all_stats) / len(all_stats),
        "avg_words_per_case": sum(s.get("total_words", 0) for s in all_stats) / len(all_stats),
        "processing_time": processing_time,
        "avg_processing_time_per_case": processing_time / len(successful_cases) if successful_cases else 0,
        "cases_per_minute": len(successful_cases) / (processing_time / 60) if processing_time > 0 else 0
    }