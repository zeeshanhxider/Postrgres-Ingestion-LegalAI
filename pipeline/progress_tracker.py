"""
Progress Tracker for Production Pipeline
Provides checkpoint/resume capability and failed file tracking for overnight runs.

Features:
- Checkpoint save/load for resume after interruption
- Failed files CSV for later retry
- Real-time progress logging with ETA
- Graceful shutdown handling (Ctrl+C)
"""

import csv
import json
import logging
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Track pipeline progress with checkpoint/resume and failure logging.
    
    Files created:
    1. checkpoint_{job_name}.json - Current progress state
    2. failed_{job_name}.csv - Detailed failure log for retry
    """
    
    def __init__(
        self,
        output_dir: str = "logs",
        job_name: Optional[str] = None,
        auto_save_interval: int = 1,  # Save after every file by default
        backup_interval: int = 50     # Backup checkpoint every N files
    ):
        """
        Initialize progress tracker.
        
        Args:
            output_dir: Directory for checkpoint and failed files
            job_name: Unique name for this job (default: timestamp)
            auto_save_interval: Save checkpoint every N files (default: 1 = every file)
            backup_interval: Create backup checkpoint every N files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate job name if not provided
        if job_name:
            self.job_name = job_name
        else:
            self.job_name = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.checkpoint_file = self.output_dir / f"checkpoint_{self.job_name}.json"
        self.checkpoint_backup = self.output_dir / f"checkpoint_{self.job_name}.backup.json"
        self.checkpoint_temp = self.output_dir / f"checkpoint_{self.job_name}.tmp"
        self.failed_file = self.output_dir / f"failed_{self.job_name}.csv"
        
        self.auto_save_interval = auto_save_interval
        self.backup_interval = backup_interval
        self.files_since_backup = 0
        
        # State
        self.processed_files: Set[str] = set()
        self.extracted_files: Set[str] = set()  # Track extraction separate from insert
        self.pending_inserts: Set[str] = set()  # Files extracted but not yet inserted
        self.failed_files: List[Dict] = []
        self.stats = {
            'extracted': 0,
            'inserted': 0,
            'duplicates': 0,
            'failed_extraction': 0,
            'failed_insert': 0,
        }
        
        # Timing
        self.start_time: Optional[datetime] = None
        self.total_files: int = 0
        self.files_since_save: int = 0
        
        # Shutdown handling
        self._shutdown_requested = False
        self._lock = threading.RLock()  # RLock allows same thread to acquire multiple times
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.warning(f"\n[!] Shutdown signal received, saving checkpoint...")
            self._shutdown_requested = True
            self.save_checkpoint()
            logger.info("[OK] Checkpoint saved. Safe to exit.")
        
        # Only set handlers in main thread
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # Not in main thread, skip signal handling
            pass
    
    def should_shutdown(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_requested
    
    def load_checkpoint(self, checkpoint_path: Optional[str] = None) -> bool:
        """
        Load progress from checkpoint file.
        
        Args:
            checkpoint_path: Path to checkpoint file (default: auto-detect)
            
        Returns:
            True if checkpoint loaded successfully
        """
        path = Path(checkpoint_path) if checkpoint_path else self.checkpoint_file
        
        if not path.exists():
            return False
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.job_name = data.get('job_name', self.job_name)
            self.processed_files = set(data.get('processed_files', []))
            self.extracted_files = set(data.get('extracted_files', []))
            self.pending_inserts = set(data.get('pending_inserts', []))
            self.stats = data.get('stats', self.stats)
            
            logger.info(f"[OK] Loaded checkpoint: {len(self.processed_files)} files fully processed")
            if self.pending_inserts:
                logger.info(f"  [!] {len(self.pending_inserts)} files extracted but pending insert")
            logger.info(f"  Stats: extracted={self.stats['extracted']}, inserted={self.stats['inserted']}, failed={self.stats['failed_extraction'] + self.stats['failed_insert']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return False
    
    def save_checkpoint(self, force_backup: bool = False):
        """Save current progress to checkpoint file using atomic write."""
        with self._lock:
            data = {
                'job_name': self.job_name,
                'processed_files': list(self.processed_files),
                'extracted_files': list(self.extracted_files),
                'pending_inserts': list(self.pending_inserts),
                'stats': self.stats,
                'last_updated': datetime.now().isoformat(),
                'total_files': self.total_files,
                'processed_count': len(self.processed_files),
            }
            
            try:
                # Atomic write: write to temp file, then rename
                with open(self.checkpoint_temp, 'w') as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    import os
                    os.fsync(f.fileno())  # Force write to disk
                
                # Rename temp to actual (atomic on most systems)
                import shutil
                shutil.move(str(self.checkpoint_temp), str(self.checkpoint_file))
                
                self.files_since_save = 0
                self.files_since_backup += 1
                
                # Create backup periodically
                if force_backup or self.files_since_backup >= self.backup_interval:
                    try:
                        shutil.copy2(str(self.checkpoint_file), str(self.checkpoint_backup))
                        self.files_since_backup = 0
                        logger.debug(f"Backup checkpoint saved: {self.checkpoint_backup}")
                    except Exception as be:
                        logger.warning(f"Failed to create backup checkpoint: {be}")
                        
            except Exception as e:
                logger.error(f"Failed to save checkpoint: {e}")
                # Try direct write as fallback
                try:
                    with open(self.checkpoint_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    logger.info("Checkpoint saved via fallback method")
                except Exception as e2:
                    logger.error(f"Fallback checkpoint save also failed: {e2}")
    
    def start_job(self, total_files: int):
        """
        Start tracking a new job.
        
        Args:
            total_files: Total number of files to process
        """
        self.total_files = total_files
        self.start_time = datetime.now()
        
        # Log job info
        already_done = len(self.processed_files)
        remaining = total_files - already_done
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Job: {self.job_name}")
        logger.info(f"Total files: {total_files}")
        logger.info(f"Already processed: {already_done}")
        logger.info(f"Remaining: {remaining}")
        logger.info(f"Checkpoint: {self.checkpoint_file}")
        logger.info(f"Failed log: {self.failed_file}")
        logger.info(f"{'='*60}\n")
    
    def get_unprocessed_files(self, all_files: List[str]) -> List[str]:
        """
        Filter out already-processed files.
        
        Args:
            all_files: List of all file paths
            
        Returns:
            List of files not yet processed
        """
        # Normalize paths for comparison
        processed_normalized = {str(Path(p).resolve()) for p in self.processed_files}
        
        unprocessed = []
        for f in all_files:
            if str(Path(f).resolve()) not in processed_normalized:
                unprocessed.append(f)
        
        return unprocessed
    
    def mark_extraction_success(self, file_path: str):
        """
        Mark a file as successfully extracted (pending insert).
        This allows recovery if insert fails later.
        
        Args:
            file_path: Path to the extracted file
        """
        with self._lock:
            path_str = str(file_path)
            self.extracted_files.add(path_str)
            self.pending_inserts.add(path_str)
            # Save immediately to ensure extraction progress is recorded
            self.save_checkpoint()
    
    def mark_success(
        self,
        file_path: str,
        case_id: int,
        was_duplicate: bool = False
    ):
        """
        Mark a file as successfully processed (extracted + inserted).
        
        Args:
            file_path: Path to the processed file
            case_id: ID of the inserted case
            was_duplicate: True if case was updated (not new insert)
        """
        with self._lock:
            path_str = str(file_path)
            self.processed_files.add(path_str)
            # Remove from pending since insert succeeded
            self.pending_inserts.discard(path_str)
            self.stats['extracted'] += 1
            
            if was_duplicate:
                self.stats['duplicates'] += 1
            else:
                self.stats['inserted'] += 1
            
            self.files_since_save += 1
            
            # Auto-save checkpoint (default: every file)
            if self.files_since_save >= self.auto_save_interval:
                self.save_checkpoint()
                
            # Log checkpoint save for visibility every 100 files
            if len(self.processed_files) % 100 == 0:
                logger.info(f"[CHECKPOINT] {len(self.processed_files)} files saved to {self.checkpoint_file}")
        
        # Log progress
        self._log_progress(file_path, case_id, was_duplicate)
    
    def mark_failed(
        self,
        file_path: str,
        error: str,
        stage: str = "unknown",
        metadata_row: Optional[Dict] = None
    ):
        """
        Mark a file as failed.
        
        Args:
            file_path: Path to the failed file
            error: Error message
            stage: Which stage failed (extraction, insert, rag)
            metadata_row: Optional metadata for the file
        """
        with self._lock:
            # Still mark as processed to skip on retry
            self.processed_files.add(str(file_path))
            
            if stage == "extraction":
                self.stats['failed_extraction'] += 1
            else:
                self.stats['failed_insert'] += 1
            
            # Record failure details
            failure = {
                'timestamp': datetime.now().isoformat(),
                'file_path': str(file_path),
                'stage': stage,
                'error': str(error)[:500],  # Truncate long errors
                'case_number': metadata_row.get('case_number', '') if metadata_row else '',
                'case_title': metadata_row.get('case_title', '') if metadata_row else '',
            }
            self.failed_files.append(failure)
            
            # Write to CSV immediately
            self._write_failed_csv(failure)
            
            self.files_since_save += 1
            if self.files_since_save >= self.auto_save_interval:
                self.save_checkpoint()
                
        # Log
        filename = Path(file_path).name
        done = len(self.processed_files)
        logger.warning(f"[{done}/{self.total_files}] [FAIL] {stage}: {filename} - {str(error)[:100]}")
        logger.info(f"[CHECKPOINT] Failure recorded, checkpoint saved ({len(self.processed_files)} total)")
    
    def _write_failed_csv(self, failure: Dict):
        """Append a failure to the CSV file."""
        file_exists = self.failed_file.exists()
        
        try:
            with open(self.failed_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'file_path', 'stage', 'error', 'case_number', 'case_title'
                ])
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(failure)
        except Exception as e:
            logger.error(f"Failed to write to failed CSV: {e}")
    
    def _log_progress(self, file_path: str, case_id: int, was_duplicate: bool):
        """Log progress with ETA."""
        done = len(self.processed_files)
        remaining = self.total_files - done
        
        # Calculate ETA
        eta_str = ""
        if self.start_time and done > 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            avg_time = elapsed / done
            eta_seconds = avg_time * remaining
            
            if eta_seconds < 60:
                eta_str = f"{int(eta_seconds)}s"
            elif eta_seconds < 3600:
                eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
            else:
                hours = int(eta_seconds // 3600)
                mins = int((eta_seconds % 3600) // 60)
                eta_str = f"{hours}h {mins}m"
        
        filename = Path(file_path).name
        status = "[OK] DUPLICATE" if was_duplicate else "[OK] INSERTED"
        
        logger.info(f"[{done}/{self.total_files}] {status} (case_id={case_id}) {filename} | ETA: {eta_str}")
    
    def finish_job(self):
        """Complete the job and save final state."""
        self.save_checkpoint()
        
        duration = ""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed < 60:
                duration = f"{int(elapsed)}s"
            elif elapsed < 3600:
                duration = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
            else:
                hours = int(elapsed // 3600)
                mins = int((elapsed % 3600) // 60)
                duration = f"{hours}h {mins}m"
        
        total_failed = self.stats['failed_extraction'] + self.stats['failed_insert']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Job Complete: {self.job_name}")
        logger.info(f"{'='*60}")
        logger.info(f"Total processed: {len(self.processed_files)}/{self.total_files}")
        logger.info(f"Extracted: {self.stats['extracted']}")
        logger.info(f"Inserted (new): {self.stats['inserted']}")
        logger.info(f"Duplicates (updated): {self.stats['duplicates']}")
        logger.info(f"Failed extraction: {self.stats['failed_extraction']}")
        logger.info(f"Failed insert: {self.stats['failed_insert']}")
        logger.info(f"Duration: {duration}")
        
        if total_failed > 0:
            logger.info(f"\n[!] {total_failed} failures logged to: {self.failed_file}")
            logger.info(f"    Run with --retry-failed {self.failed_file} to retry")
        
        logger.info(f"\n[OK] Checkpoint saved: {self.checkpoint_file}")


def load_failed_files_csv(csv_path: str) -> List[str]:
    """
    Load failed file paths from a failed files CSV for retry.
    
    Args:
        csv_path: Path to failed files CSV
        
    Returns:
        List of file paths to retry
    """
    failed_paths = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('file_path'):
                    failed_paths.append(row['file_path'])
    except Exception as e:
        logger.error(f"Failed to read failed files CSV: {e}")
    
    return failed_paths
