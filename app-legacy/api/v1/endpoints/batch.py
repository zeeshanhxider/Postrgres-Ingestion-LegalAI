"""
Batch Processing API endpoints for PDF ingestion
Provides API access to the batch processing functionality
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, UploadFile, File
from typing import Optional, List
from pydantic import BaseModel
import os
import tempfile
import shutil
from pathlib import Path

from app.services.case_ingestor import LegalCaseIngestor
from app.database import engine

router = APIRouter()

# Response models
class BatchProcessingStatus(BaseModel):
    job_id: str
    status: str  # "running", "completed", "failed"
    processed_files: int
    total_files: int
    current_file: Optional[str]
    message: str

class ProcessingResult(BaseModel):
    success: bool
    case_id: Optional[str]
    filename: str
    message: str
    processing_time: Optional[float]

class BatchResult(BaseModel):
    job_id: str
    total_files: int
    successful: int
    failed: int
    results: List[ProcessingResult]

# Global job storage (in production, use Redis or database)
_active_jobs = {}
_completed_jobs = {}

@router.post("/upload-pdfs")
async def upload_pdfs_for_processing(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    enable_ai_extraction: bool = Query(True, description="Enable AI extraction")
):
    """
    Upload multiple PDF files for batch processing
    
    Files are processed in the background and results can be retrieved
    using the returned job_id
    """
    import uuid
    from datetime import datetime
    
    job_id = str(uuid.uuid4())
    
    # Save uploaded files to temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    saved_files = []
    
    try:
        for file in files:
            if not file.filename.endswith('.pdf'):
                continue
                
            file_path = temp_dir / file.filename
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file.file, f)
            saved_files.append(file_path)
        
        if not saved_files:
            raise HTTPException(status_code=400, detail="No valid PDF files uploaded")
        
        # Initialize job status
        _active_jobs[job_id] = {
            "status": "running",
            "processed_files": 0,
            "total_files": len(saved_files),
            "current_file": None,
            "message": "Processing started",
            "start_time": datetime.now()
        }
        
        # Start background processing
        background_tasks.add_task(
            _process_pdf_batch,
            job_id,
            saved_files,
            temp_dir,
            enable_ai_extraction
        )
        
        return {
            "job_id": job_id,
            "status": "running",
            "total_files": len(saved_files),
            "message": f"Started processing {len(saved_files)} files"
        }
        
    except Exception as e:
        # Cleanup on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{job_id}", response_model=BatchProcessingStatus)
async def get_processing_status(job_id: str):
    """
    Get the status of a batch processing job
    """
    if job_id in _active_jobs:
        job_data = _active_jobs[job_id]
        return BatchProcessingStatus(
            job_id=job_id,
            **job_data
        )
    elif job_id in _completed_jobs:
        job_data = _completed_jobs[job_id]
        return BatchProcessingStatus(
            job_id=job_id,
            **job_data
        )
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@router.get("/results/{job_id}", response_model=BatchResult)
async def get_processing_results(job_id: str):
    """
    Get the detailed results of a completed batch processing job
    """
    if job_id in _completed_jobs:
        return _completed_jobs[job_id]["detailed_results"]
    elif job_id in _active_jobs:
        raise HTTPException(status_code=425, detail="Job still running")
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@router.post("/process-single")
async def process_single_pdf(
    file: UploadFile = File(...),
    enable_ai_extraction: bool = Query(True, description="Enable AI extraction")
):
    """
    Process a single PDF file immediately (synchronous)
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Read file content
        pdf_content = await file.read()
        
        # Prepare metadata
        metadata = {
            'case_number': Path(file.filename).stem,
            'title': Path(file.filename).stem.replace('_', ' ').title(),
            'court_level': 'Appeals',
            'division': 'Unknown',
            'publication': 'Unknown'
        }
        
        # Prepare source file info
        source_file_info = {
            'filename': file.filename,
            'file_path': f'uploaded/{file.filename}'
        }
        
        # Process with case ingestor
        ingestor = LegalCaseIngestor(engine)
        result = ingestor.ingest_pdf_case(
            pdf_content=pdf_content,
            metadata=metadata,
            source_file_info=source_file_info,
            enable_ai_extraction=enable_ai_extraction
        )
        
        return {
            "success": True,
            "case_id": result['case_id'],
            "filename": file.filename,
            "message": "PDF processed successfully",
            "ai_extraction": result.get('ai_extraction', False),
            "statistics": result.get('case_stats', {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-jobs")
async def get_active_jobs():
    """
    Get list of currently active batch processing jobs
    """
    return {
        "active_jobs": [
            {
                "job_id": job_id,
                "status": job_data["status"],
                "progress": f"{job_data['processed_files']}/{job_data['total_files']}"
            }
            for job_id, job_data in _active_jobs.items()
        ]
    }

# Background task function
async def _process_pdf_batch(
    job_id: str,
    pdf_files: List[Path],
    temp_dir: Path,
    enable_ai_extraction: bool
):
    """
    Background task to process a batch of PDF files
    """
    from datetime import datetime
    import time
    
    ingestor = LegalCaseIngestor(engine)
    results = []
    successful = 0
    failed = 0
    
    try:
        for i, pdf_path in enumerate(pdf_files):
            # Update job status
            _active_jobs[job_id].update({
                "processed_files": i,
                "current_file": pdf_path.name,
                "message": f"Processing {pdf_path.name}"
            })
            
            start_time = time.time()
            
            try:
                # Read PDF content
                with open(pdf_path, 'rb') as f:
                    pdf_content = f.read()
                
                # Prepare metadata
                metadata = {
                    'case_number': pdf_path.stem,
                    'title': pdf_path.stem.replace('_', ' ').title(),
                    'court_level': 'Appeals',
                    'division': 'Unknown',
                    'publication': 'Unknown'
                }
                
                # Prepare source file info
                source_file_info = {
                    'filename': pdf_path.name,
                    'file_path': str(pdf_path)
                }
                
                # Process PDF
                result = ingestor.ingest_pdf_case(
                    pdf_content=pdf_content,
                    metadata=metadata,
                    source_file_info=source_file_info,
                    enable_ai_extraction=enable_ai_extraction
                )
                
                processing_time = time.time() - start_time
                
                results.append(ProcessingResult(
                    success=True,
                    case_id=result['case_id'],
                    filename=pdf_path.name,
                    message="Successfully processed",
                    processing_time=processing_time
                ))
                successful += 1
                
            except Exception as e:
                processing_time = time.time() - start_time
                
                results.append(ProcessingResult(
                    success=False,
                    case_id=None,
                    filename=pdf_path.name,
                    message=str(e),
                    processing_time=processing_time
                ))
                failed += 1
        
        # Mark job as completed
        final_result = BatchResult(
            job_id=job_id,
            total_files=len(pdf_files),
            successful=successful,
            failed=failed,
            results=results
        )
        
        _completed_jobs[job_id] = {
            "status": "completed",
            "processed_files": len(pdf_files),
            "total_files": len(pdf_files),
            "current_file": None,
            "message": f"Completed: {successful} successful, {failed} failed",
            "detailed_results": final_result
        }
        
        # Remove from active jobs
        del _active_jobs[job_id]
        
    except Exception as e:
        # Mark job as failed
        _completed_jobs[job_id] = {
            "status": "failed",
            "processed_files": len(results),
            "total_files": len(pdf_files),
            "current_file": None,
            "message": str(e),
            "detailed_results": None
        }
        
        if job_id in _active_jobs:
            del _active_jobs[job_id]
    
    finally:
        # Cleanup temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)
