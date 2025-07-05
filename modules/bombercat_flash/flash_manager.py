"""Flash manager for coordinating firmware flashing operations."""

import asyncio
import logging
from typing import Dict, Optional, Callable, Any
from uuid import UUID
from enum import Enum

from core.entities.device import Device, DeviceStatus
from core.entities.firmware import Firmware
from core.use_cases.device_flashing import FlashingProgress, FlashingStatus
from infrastructure.esptool_adapter import ESPToolAdapter


logger = logging.getLogger(__name__)


class FlashJobStatus(Enum):
    """Status of a flash job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FlashJob:
    """Represents a firmware flashing job."""
    
    def __init__(
        self,
        job_id: str,
        device: Device,
        firmware: Firmware,
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ):
        self.job_id = job_id
        self.device = device
        self.firmware = firmware
        self.progress_callback = progress_callback
        self.status = FlashJobStatus.QUEUED
        self.error_message: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.progress: FlashingProgress = FlashingProgress(
            status=FlashingStatus.PREPARING,
            progress_percent=0.0,
            message="Job queued"
        )


class FlashManager:
    """Manages firmware flashing operations and job queue."""
    
    def __init__(self, max_concurrent_jobs: int = 1):
        self.max_concurrent_jobs = max_concurrent_jobs
        self._jobs: Dict[str, FlashJob] = {}
        self._job_queue: asyncio.Queue = asyncio.Queue()
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Flash adapters for different device types
        self._flash_adapters = {
            "esp32": ESPToolAdapter(),
            "esp8266": ESPToolAdapter(),
        }
    
    async def start(self) -> None:
        """Start the flash manager worker."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Flash manager started")
    
    async def stop(self) -> None:
        """Stop the flash manager and cancel running jobs."""
        self._shutdown_event.set()
        
        # Cancel running jobs
        for job_id, task in self._running_jobs.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled flash job: {job_id}")
        
        # Wait for worker to finish
        if self._worker_task and not self._worker_task.done():
            await self._worker_task
        
        logger.info("Flash manager stopped")
    
    async def queue_flash_job(
        self,
        device: Device,
        firmware: Firmware,
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ) -> str:
        """Queue a new flash job."""
        job_id = f"flash_{device.id}_{firmware.id}"
        
        # Check if device is already being flashed
        if self._is_device_being_flashed(device.id):
            raise ValueError(f"Device {device.id} is already being flashed")
        
        # Create flash job
        job = FlashJob(
            job_id=job_id,
            device=device,
            firmware=firmware,
            progress_callback=progress_callback,
        )
        
        self._jobs[job_id] = job
        await self._job_queue.put(job)
        
        logger.info(f"Queued flash job: {job_id}")
        return job_id
    
    async def cancel_flash_job(self, job_id: str) -> bool:
        """Cancel a flash job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        if job.status == FlashJobStatus.RUNNING:
            # Cancel running task
            task = self._running_jobs.get(job_id)
            if task and not task.done():
                task.cancel()
                job.status = FlashJobStatus.CANCELLED
                logger.info(f"Cancelled running flash job: {job_id}")
                return True
        elif job.status == FlashJobStatus.QUEUED:
            # Mark as cancelled (will be skipped by worker)
            job.status = FlashJobStatus.CANCELLED
            logger.info(f"Cancelled queued flash job: {job_id}")
            return True
        
        return False
    
    def get_job_status(self, job_id: str) -> Optional[FlashJob]:
        """Get status of a flash job."""
        return self._jobs.get(job_id)
    
    def get_all_jobs(self) -> Dict[str, FlashJob]:
        """Get all flash jobs."""
        return self._jobs.copy()
    
    def get_running_jobs(self) -> Dict[str, FlashJob]:
        """Get currently running flash jobs."""
        return {
            job_id: job for job_id, job in self._jobs.items()
            if job.status == FlashJobStatus.RUNNING
        }
    
    def _is_device_being_flashed(self, device_id: UUID) -> bool:
        """Check if device is currently being flashed."""
        for job in self._jobs.values():
            if (
                job.device.id == device_id
                and job.status in [FlashJobStatus.QUEUED, FlashJobStatus.RUNNING]
            ):
                return True
        return False
    
    async def _worker(self) -> None:
        """Main worker loop for processing flash jobs."""
        logger.info("Flash manager worker started")
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for job or shutdown
                try:
                    job = await asyncio.wait_for(
                        self._job_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Skip cancelled jobs
                if job.status == FlashJobStatus.CANCELLED:
                    continue
                
                # Check if we can start new job
                if len(self._running_jobs) >= self.max_concurrent_jobs:
                    # Put job back in queue
                    await self._job_queue.put(job)
                    await asyncio.sleep(0.1)
                    continue
                
                # Start flash job
                task = asyncio.create_task(self._execute_flash_job(job))
                self._running_jobs[job.job_id] = task
                
                # Clean up completed tasks
                await self._cleanup_completed_tasks()
            
            except Exception as e:
                logger.error(f"Error in flash manager worker: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("Flash manager worker stopped")
    
    async def _execute_flash_job(self, job: FlashJob) -> None:
        """Execute a flash job."""
        job.status = FlashJobStatus.RUNNING
        job.start_time = asyncio.get_event_loop().time()
        
        logger.info(f"Starting flash job: {job.job_id}")
        
        try:
            # Get appropriate flash adapter
            adapter = self._get_flash_adapter(job.device)
            if not adapter:
                raise ValueError(f"No flash adapter for device type: {job.device.device_type}")
            
            # Create progress callback wrapper
            def progress_wrapper(progress: FlashingProgress) -> None:
                job.progress = progress
                if job.progress_callback:
                    job.progress_callback(progress)
            
            # Execute flashing
            success = await adapter.flash_firmware(
                job.device,
                job.firmware,
                progress_wrapper
            )
            
            if success:
                job.status = FlashJobStatus.COMPLETED
                job.progress = FlashingProgress(
                    status=FlashingStatus.COMPLETED,
                    progress_percent=100.0,
                    message="Firmware flashed successfully"
                )
                logger.info(f"Flash job completed successfully: {job.job_id}")
            else:
                job.status = FlashJobStatus.FAILED
                job.error_message = "Flash operation failed"
                job.progress = FlashingProgress(
                    status=FlashingStatus.FAILED,
                    error="Flash operation failed"
                )
                logger.error(f"Flash job failed: {job.job_id}")
        
        except asyncio.CancelledError:
            job.status = FlashJobStatus.CANCELLED
            job.error_message = "Job was cancelled"
            logger.info(f"Flash job cancelled: {job.job_id}")
            raise
        
        except Exception as e:
            job.status = FlashJobStatus.FAILED
            job.error_message = str(e)
            job.progress = FlashingProgress(
                status=FlashingStatus.FAILED,
                error=str(e)
            )
            logger.error(f"Flash job failed with error: {job.job_id} - {e}")
        
        finally:
            job.end_time = asyncio.get_event_loop().time()
            # Remove from running jobs
            self._running_jobs.pop(job.job_id, None)
    
    def _get_flash_adapter(self, device: Device) -> Optional[Any]:
        """Get appropriate flash adapter for device type."""
        device_type = device.device_type.value.lower()
        return self._flash_adapters.get(device_type)
    
    async def _cleanup_completed_tasks(self) -> None:
        """Clean up completed tasks from running jobs."""
        completed_jobs = []
        
        for job_id, task in self._running_jobs.items():
            if task.done():
                completed_jobs.append(job_id)
        
        for job_id in completed_jobs:
            self._running_jobs.pop(job_id, None)
    
    def add_flash_adapter(self, device_type: str, adapter: Any) -> None:
        """Add a flash adapter for a device type."""
        self._flash_adapters[device_type.lower()] = adapter
        logger.info(f"Added flash adapter for device type: {device_type}")
    
    def remove_flash_adapter(self, device_type: str) -> None:
        """Remove flash adapter for a device type."""
        self._flash_adapters.pop(device_type.lower(), None)
        logger.info(f"Removed flash adapter for device type: {device_type}")
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._job_queue.qsize()
    
    def get_running_count(self) -> int:
        """Get number of currently running jobs."""
        return len(self._running_jobs)