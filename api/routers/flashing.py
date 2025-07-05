"""Device flashing API endpoints."""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.entities.device import Device
from core.entities.firmware import Firmware
from core.use_cases.device_flashing import FlashingProgress
from modules.bombercat_flash import FlashService, ProgressTracker
from modules.bombercat_flash.flash_manager import FlashJob, FlashJobStatus
from api.dependencies import get_flash_service, get_progress_tracker


logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for API
class FlashingProgressResponse(BaseModel):
    """Flashing progress response model."""
    bytes_written: int
    total_bytes: int
    percentage: float
    current_operation: str
    
    @classmethod
    def from_entity(cls, progress: FlashingProgress) -> "FlashingProgressResponse":
        """Create response from flashing progress entity."""
        return cls(
            bytes_written=progress.bytes_written,
            total_bytes=progress.total_bytes,
            percentage=progress.percentage,
            current_operation=progress.current_operation,
        )


class FlashJobResponse(BaseModel):
    """Flash job response model."""
    job_id: str
    device_id: UUID
    device_name: str
    firmware_id: UUID
    firmware_name: str
    firmware_version: str
    status: str
    progress: Optional[FlashingProgressResponse] = None
    error_message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    
    @classmethod
    def from_entity(cls, job: FlashJob, progress: Optional[FlashingProgress] = None) -> "FlashJobResponse":
        """Create response from flash job entity."""
        return cls(
            job_id=job.job_id,
            device_id=job.device.id,
            device_name=job.device.name,
            firmware_id=job.firmware.id,
            firmware_name=job.firmware.name,
            firmware_version=str(job.firmware.version),
            status=job.status.value,
            progress=FlashingProgressResponse.from_entity(progress) if progress else None,
            error_message=job.error_message,
            started_at=job.started_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
        )


class FlashDeviceRequest(BaseModel):
    """Flash device request model."""
    device_id: UUID
    firmware_id: UUID


class FlashDeviceWithLatestRequest(BaseModel):
    """Flash device with latest firmware request model."""
    device_id: UUID
    firmware_name: Optional[str] = Field(None, description="Specific firmware name (optional)")


class FlashStatisticsResponse(BaseModel):
    """Flash statistics response model."""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    running_jobs: int
    queued_jobs: int


class DeviceInfoResponse(BaseModel):
    """Device information response model."""
    device_id: UUID
    device_info: Dict[str, Any]


@router.post("/flash", response_model=FlashJobResponse, status_code=202)
async def flash_device(
    request: FlashDeviceRequest,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Flash firmware to a device."""
    try:
        job_id = await flash_service.flash_device(
            device_id=request.device_id,
            firmware_id=request.firmware_id,
        )
        
        # Get job details
        job = flash_service.get_flash_job_status(job_id)
        if not job:
            raise HTTPException(status_code=500, detail="Failed to create flash job")
        
        return FlashJobResponse.from_entity(job)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error flashing device: {e}")
        raise HTTPException(status_code=500, detail="Failed to start flash operation")


@router.post("/flash-latest", response_model=FlashJobResponse, status_code=202)
async def flash_device_with_latest(
    request: FlashDeviceWithLatestRequest,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Flash device with latest compatible firmware."""
    try:
        job_id = await flash_service.flash_device_with_latest_firmware(
            device_id=request.device_id,
            firmware_name=request.firmware_name,
        )
        
        # Get job details
        job = flash_service.get_flash_job_status(job_id)
        if not job:
            raise HTTPException(status_code=500, detail="Failed to create flash job")
        
        return FlashJobResponse.from_entity(job)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error flashing device with latest firmware: {e}")
        raise HTTPException(status_code=500, detail="Failed to start flash operation")


@router.get("/jobs", response_model=List[FlashJobResponse])
async def list_flash_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    device_id: Optional[UUID] = Query(None, description="Filter by device ID"),
    flash_service: FlashService = Depends(get_flash_service),
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
):
    """List flash jobs with optional filtering."""
    try:
        if status == "running":
            jobs = flash_service.get_running_flash_jobs()
        else:
            jobs = flash_service.get_all_flash_jobs()
        
        # Filter by device ID if specified
        if device_id:
            jobs = {k: v for k, v in jobs.items() if v.device.id == device_id}
        
        # Filter by status if specified (and not "running")
        if status and status != "running":
            jobs = {k: v for k, v in jobs.items() if v.status.value == status}
        
        # Create responses with current progress
        responses = []
        for job_id, job in jobs.items():
            current_progress = progress_tracker.get_current_progress(job_id)
            responses.append(FlashJobResponse.from_entity(job, current_progress))
        
        return responses
    
    except Exception as e:
        logger.error(f"Error listing flash jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list flash jobs")


@router.get("/jobs/{job_id}", response_model=FlashJobResponse)
async def get_flash_job(
    job_id: str,
    flash_service: FlashService = Depends(get_flash_service),
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
):
    """Get details of a specific flash job."""
    try:
        job = flash_service.get_flash_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Flash job not found")
        
        # Get current progress
        current_progress = progress_tracker.get_current_progress(job_id)
        
        return FlashJobResponse.from_entity(job, current_progress)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flash job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get flash job")


@router.delete("/jobs/{job_id}", status_code=204)
async def cancel_flash_job(
    job_id: str,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Cancel a flash job."""
    try:
        success = await flash_service.cancel_flash_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Flash job not found or cannot be cancelled")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling flash job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel flash job")


@router.post("/erase/{device_id}", response_model=dict)
async def erase_device(
    device_id: UUID,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Erase device flash memory."""
    try:
        success = await flash_service.erase_device(device_id)
        
        return {
            "device_id": device_id,
            "erased": success,
            "message": "Device erased successfully" if success else "Failed to erase device"
        }
    
    except Exception as e:
        logger.error(f"Error erasing device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to erase device")


@router.post("/verify/{device_id}/{firmware_id}", response_model=dict)
async def verify_device_firmware(
    device_id: UUID,
    firmware_id: UUID,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Verify firmware on device."""
    try:
        is_valid = await flash_service.verify_device_firmware(device_id, firmware_id)
        
        return {
            "device_id": device_id,
            "firmware_id": firmware_id,
            "verified": is_valid,
            "message": "Firmware verification passed" if is_valid else "Firmware verification failed"
        }
    
    except Exception as e:
        logger.error(f"Error verifying firmware on device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify firmware")


@router.get("/device-info/{device_id}", response_model=DeviceInfoResponse)
async def get_device_info(
    device_id: UUID,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Get detailed device information."""
    try:
        device_info = await flash_service.get_device_info(device_id)
        
        return DeviceInfoResponse(
            device_id=device_id,
            device_info=device_info
        )
    
    except Exception as e:
        logger.error(f"Error getting device info for {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get device info")


@router.get("/compatible-firmware/{device_id}", response_model=List[dict])
async def get_compatible_firmware(
    device_id: UUID,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Get firmware compatible with device."""
    try:
        firmware_list = await flash_service.get_compatible_firmware(device_id)
        
        return [
            {
                "id": firmware.id,
                "name": firmware.name,
                "version": str(firmware.version),
                "firmware_type": firmware.firmware_type.value,
                "file_size": firmware.file_size,
                "description": firmware.description,
            }
            for firmware in firmware_list
        ]
    
    except Exception as e:
        logger.error(f"Error getting compatible firmware for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get compatible firmware")


@router.get("/recommended-firmware/{device_id}", response_model=dict)
async def get_recommended_firmware(
    device_id: UUID,
    flash_service: FlashService = Depends(get_flash_service),
):
    """Get recommended firmware for device."""
    try:
        firmware = await flash_service.get_recommended_firmware(device_id)
        
        if not firmware:
            return {"recommended_firmware": None}
        
        return {
            "recommended_firmware": {
                "id": firmware.id,
                "name": firmware.name,
                "version": str(firmware.version),
                "firmware_type": firmware.firmware_type.value,
                "file_size": firmware.file_size,
                "description": firmware.description,
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting recommended firmware for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommended firmware")


@router.get("/statistics", response_model=FlashStatisticsResponse)
async def get_flash_statistics(
    flash_service: FlashService = Depends(get_flash_service),
):
    """Get flash operation statistics."""
    try:
        stats = flash_service.get_flash_statistics()
        
        return FlashStatisticsResponse(
            total_jobs=stats["total_jobs"],
            completed_jobs=stats["completed_jobs"],
            failed_jobs=stats["failed_jobs"],
            cancelled_jobs=stats["cancelled_jobs"],
            running_jobs=stats["running_jobs"],
            queued_jobs=stats["queued_jobs"],
        )
    
    except Exception as e:
        logger.error(f"Error getting flash statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get flash statistics")


@router.get("/device-history/{device_id}", response_model=List[FlashJobResponse])
async def get_device_flash_history(
    device_id: UUID,
    flash_service: FlashService = Depends(get_flash_service),
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
):
    """Get flash history for a device."""
    try:
        jobs = flash_service.get_device_flash_history(device_id)
        
        # Create responses with final progress
        responses = []
        for job in jobs:
            # For completed jobs, try to get final progress
            final_progress = None
            if job.status in [FlashJobStatus.COMPLETED, FlashJobStatus.FAILED]:
                final_progress = progress_tracker.get_current_progress(job.job_id)
            
            responses.append(FlashJobResponse.from_entity(job, final_progress))
        
        return responses
    
    except Exception as e:
        logger.error(f"Error getting flash history for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get device flash history")


# WebSocket endpoint for real-time progress updates
@router.websocket("/ws/progress/{job_id}")
async def websocket_flash_progress(
    websocket: WebSocket,
    job_id: str,
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
):
    """WebSocket endpoint for real-time flash progress updates."""
    await websocket.accept()
    
    try:
        # Set up progress callback
        async def progress_callback(operation_id: str, progress: FlashingProgress, snapshot):
            if operation_id == job_id:
                try:
                    await websocket.send_json({
                        "job_id": job_id,
                        "progress": {
                            "bytes_written": progress.bytes_written,
                            "total_bytes": progress.total_bytes,
                            "percentage": progress.percentage,
                            "current_operation": progress.current_operation,
                        },
                        "timestamp": snapshot.timestamp.isoformat(),
                        "bytes_per_second": snapshot.bytes_per_second,
                        "estimated_time_remaining": (
                            snapshot.estimated_time_remaining.total_seconds()
                            if snapshot.estimated_time_remaining else None
                        ),
                    })
                except Exception as e:
                    logger.error(f"Error sending progress update: {e}")
        
        # Register callback
        progress_tracker.set_progress_callback(progress_callback)
        
        # Send initial progress if available
        current_progress = progress_tracker.get_current_progress(job_id)
        if current_progress:
            await websocket.send_json({
                "job_id": job_id,
                "progress": {
                    "bytes_written": current_progress.bytes_written,
                    "total_bytes": current_progress.total_bytes,
                    "percentage": current_progress.percentage,
                    "current_operation": current_progress.current_operation,
                },
                "timestamp": None,
                "bytes_per_second": None,
                "estimated_time_remaining": None,
            })
        
        # Keep connection alive
        while True:
            try:
                # Wait for client messages (ping/pong)
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        # Clean up callback
        progress_tracker.set_progress_callback(None)