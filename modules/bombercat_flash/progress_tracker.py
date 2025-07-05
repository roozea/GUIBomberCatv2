"""Progress tracker for monitoring flash operations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from threading import Lock

from core.use_cases.device_flashing import FlashingProgress


logger = logging.getLogger(__name__)


@dataclass
class ProgressSnapshot:
    """Snapshot of progress at a specific time."""
    timestamp: datetime
    progress: FlashingProgress
    bytes_per_second: Optional[float] = None
    estimated_time_remaining: Optional[timedelta] = None


@dataclass
class ProgressHistory:
    """History of progress for a specific operation."""
    operation_id: str
    started_at: datetime
    last_updated: datetime
    snapshots: List[ProgressSnapshot] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    final_status: Optional[str] = None
    
    def add_snapshot(self, progress: FlashingProgress) -> None:
        """Add a progress snapshot."""
        now = datetime.now()
        
        # Calculate transfer rate if we have previous data
        bytes_per_second = None
        estimated_time_remaining = None
        
        if self.snapshots and progress.bytes_written > 0:
            last_snapshot = self.snapshots[-1]
            time_diff = (now - last_snapshot.timestamp).total_seconds()
            
            if time_diff > 0:
                bytes_diff = progress.bytes_written - last_snapshot.progress.bytes_written
                bytes_per_second = bytes_diff / time_diff
                
                # Estimate time remaining
                if progress.total_bytes > 0 and bytes_per_second > 0:
                    remaining_bytes = progress.total_bytes - progress.bytes_written
                    estimated_time_remaining = timedelta(seconds=remaining_bytes / bytes_per_second)
        
        snapshot = ProgressSnapshot(
            timestamp=now,
            progress=progress,
            bytes_per_second=bytes_per_second,
            estimated_time_remaining=estimated_time_remaining,
        )
        
        self.snapshots.append(snapshot)
        self.last_updated = now
        
        # Keep only last 100 snapshots to prevent memory issues
        if len(self.snapshots) > 100:
            self.snapshots = self.snapshots[-100:]
    
    def mark_completed(self, status: str) -> None:
        """Mark the operation as completed."""
        self.completed_at = datetime.now()
        self.final_status = status
    
    def get_average_speed(self, last_n_snapshots: int = 10) -> Optional[float]:
        """Get average transfer speed from last N snapshots."""
        if len(self.snapshots) < 2:
            return None
        
        recent_snapshots = self.snapshots[-last_n_snapshots:]
        if len(recent_snapshots) < 2:
            return None
        
        total_bytes = recent_snapshots[-1].progress.bytes_written - recent_snapshots[0].progress.bytes_written
        total_time = (recent_snapshots[-1].timestamp - recent_snapshots[0].timestamp).total_seconds()
        
        if total_time > 0:
            return total_bytes / total_time
        return None
    
    def get_current_speed(self) -> Optional[float]:
        """Get current transfer speed."""
        if not self.snapshots:
            return None
        return self.snapshots[-1].bytes_per_second
    
    def get_estimated_time_remaining(self) -> Optional[timedelta]:
        """Get estimated time remaining."""
        if not self.snapshots:
            return None
        return self.snapshots[-1].estimated_time_remaining
    
    def get_duration(self) -> timedelta:
        """Get total duration of the operation."""
        end_time = self.completed_at or datetime.now()
        return end_time - self.started_at


class ProgressTracker:
    """Tracks progress of multiple flash operations."""
    
    def __init__(self, max_history_entries: int = 1000):
        self._max_history_entries = max_history_entries
        self._active_operations: Dict[str, ProgressHistory] = {}
        self._completed_operations: Dict[str, ProgressHistory] = {}
        self._lock = Lock()
        
        # Event callbacks
        self._on_progress_updated: Optional[Callable[[str, FlashingProgress, ProgressSnapshot], None]] = None
        self._on_operation_completed: Optional[Callable[[str, ProgressHistory], None]] = None
    
    def start_tracking(self, operation_id: str) -> None:
        """Start tracking progress for an operation."""
        with self._lock:
            if operation_id in self._active_operations:
                logger.warning(f"Operation {operation_id} is already being tracked")
                return
            
            history = ProgressHistory(
                operation_id=operation_id,
                started_at=datetime.now(),
                last_updated=datetime.now(),
            )
            
            self._active_operations[operation_id] = history
            logger.debug(f"Started tracking operation: {operation_id}")
    
    def update_progress(self, operation_id: str, progress: FlashingProgress) -> None:
        """Update progress for an operation."""
        with self._lock:
            if operation_id not in self._active_operations:
                # Auto-start tracking if not already started
                self.start_tracking(operation_id)
            
            history = self._active_operations[operation_id]
            history.add_snapshot(progress)
            
            # Get the latest snapshot for callback
            latest_snapshot = history.snapshots[-1] if history.snapshots else None
            
        # Call callback outside of lock
        if self._on_progress_updated and latest_snapshot:
            try:
                self._on_progress_updated(operation_id, progress, latest_snapshot)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def complete_operation(self, operation_id: str, status: str = "completed") -> None:
        """Mark an operation as completed."""
        with self._lock:
            if operation_id not in self._active_operations:
                logger.warning(f"Operation {operation_id} is not being tracked")
                return
            
            history = self._active_operations.pop(operation_id)
            history.mark_completed(status)
            
            # Move to completed operations
            self._completed_operations[operation_id] = history
            
            # Limit completed operations history
            if len(self._completed_operations) > self._max_history_entries:
                # Remove oldest entries
                oldest_keys = sorted(
                    self._completed_operations.keys(),
                    key=lambda k: self._completed_operations[k].started_at
                )
                for key in oldest_keys[:-self._max_history_entries]:
                    del self._completed_operations[key]
        
        # Call callback outside of lock
        if self._on_operation_completed:
            try:
                self._on_operation_completed(operation_id, history)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")
        
        logger.debug(f"Completed tracking operation: {operation_id} with status: {status}")
    
    def get_active_operations(self) -> Dict[str, ProgressHistory]:
        """Get all active operations."""
        with self._lock:
            return self._active_operations.copy()
    
    def get_completed_operations(self) -> Dict[str, ProgressHistory]:
        """Get all completed operations."""
        with self._lock:
            return self._completed_operations.copy()
    
    def get_operation_history(self, operation_id: str) -> Optional[ProgressHistory]:
        """Get history for a specific operation."""
        with self._lock:
            if operation_id in self._active_operations:
                return self._active_operations[operation_id]
            return self._completed_operations.get(operation_id)
    
    def get_current_progress(self, operation_id: str) -> Optional[FlashingProgress]:
        """Get current progress for an operation."""
        history = self.get_operation_history(operation_id)
        if history and history.snapshots:
            return history.snapshots[-1].progress
        return None
    
    def get_operation_statistics(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for an operation."""
        history = self.get_operation_history(operation_id)
        if not history:
            return None
        
        stats = {
            "operation_id": operation_id,
            "started_at": history.started_at,
            "last_updated": history.last_updated,
            "completed_at": history.completed_at,
            "final_status": history.final_status,
            "duration": history.get_duration(),
            "snapshot_count": len(history.snapshots),
            "current_speed": history.get_current_speed(),
            "average_speed": history.get_average_speed(),
            "estimated_time_remaining": history.get_estimated_time_remaining(),
        }
        
        if history.snapshots:
            latest = history.snapshots[-1]
            stats.update({
                "current_progress": latest.progress,
                "bytes_written": latest.progress.bytes_written,
                "total_bytes": latest.progress.total_bytes,
                "percentage": latest.progress.percentage,
                "current_operation": latest.progress.current_operation,
            })
        
        return stats
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global statistics for all operations."""
        with self._lock:
            active_count = len(self._active_operations)
            completed_count = len(self._completed_operations)
            
            # Calculate success rate
            successful_operations = sum(
                1 for history in self._completed_operations.values()
                if history.final_status == "completed"
            )
            
            success_rate = (
                successful_operations / completed_count * 100
                if completed_count > 0 else 0
            )
            
            # Calculate average duration for completed operations
            if completed_count > 0:
                total_duration = sum(
                    history.get_duration().total_seconds()
                    for history in self._completed_operations.values()
                )
                average_duration = timedelta(seconds=total_duration / completed_count)
            else:
                average_duration = timedelta(0)
        
        return {
            "active_operations": active_count,
            "completed_operations": completed_count,
            "total_operations": active_count + completed_count,
            "success_rate": success_rate,
            "successful_operations": successful_operations,
            "average_duration": average_duration,
        }
    
    def clear_completed_operations(self) -> None:
        """Clear all completed operations from history."""
        with self._lock:
            cleared_count = len(self._completed_operations)
            self._completed_operations.clear()
        
        logger.info(f"Cleared {cleared_count} completed operations from history")
    
    def set_progress_callback(
        self, callback: Callable[[str, FlashingProgress, ProgressSnapshot], None]
    ) -> None:
        """Set callback for progress updates."""
        self._on_progress_updated = callback
    
    def set_completion_callback(
        self, callback: Callable[[str, ProgressHistory], None]
    ) -> None:
        """Set callback for operation completion."""
        self._on_operation_completed = callback
    
    def export_operation_data(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Export all data for an operation."""
        history = self.get_operation_history(operation_id)
        if not history:
            return None
        
        return {
            "operation_id": operation_id,
            "started_at": history.started_at.isoformat(),
            "last_updated": history.last_updated.isoformat(),
            "completed_at": history.completed_at.isoformat() if history.completed_at else None,
            "final_status": history.final_status,
            "snapshots": [
                {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "bytes_written": snapshot.progress.bytes_written,
                    "total_bytes": snapshot.progress.total_bytes,
                    "percentage": snapshot.progress.percentage,
                    "current_operation": snapshot.progress.current_operation,
                    "bytes_per_second": snapshot.bytes_per_second,
                    "estimated_time_remaining": (
                        snapshot.estimated_time_remaining.total_seconds()
                        if snapshot.estimated_time_remaining else None
                    ),
                }
                for snapshot in history.snapshots
            ],
        }