"""Flash service for high-level firmware flashing operations."""

import logging
from typing import List, Optional, Callable, Dict, Any
from uuid import UUID

from core.entities.device import Device
from core.entities.firmware import Firmware
from core.use_cases.device_flashing import DeviceFlashingUseCase, FlashingProgress
from modules.bombercat_flash.flash_manager import FlashManager, FlashJob
from modules.bombercat_flash.progress_tracker import ProgressTracker


logger = logging.getLogger(__name__)


class FlashService:
    """High-level service for firmware flashing operations."""
    
    def __init__(
        self,
        device_flashing_use_case: DeviceFlashingUseCase,
        flash_manager: FlashManager,
        progress_tracker: Optional[ProgressTracker] = None,
    ):
        self._device_flashing_use_case = device_flashing_use_case
        self._flash_manager = flash_manager
        self._progress_tracker = progress_tracker or ProgressTracker()
        
        # Event callbacks
        self._on_flash_started: Optional[Callable[[str, Device, Firmware], None]] = None
        self._on_flash_completed: Optional[Callable[[str, Device, Firmware, bool], None]] = None
        self._on_flash_progress: Optional[Callable[[str, FlashingProgress], None]] = None
    
    async def start(self) -> None:
        """Start the flash service."""
        await self._flash_manager.start()
        logger.info("Flash service started")
    
    async def stop(self) -> None:
        """Stop the flash service."""
        await self._flash_manager.stop()
        logger.info("Flash service stopped")
    
    async def flash_device(
        self,
        device_id: UUID,
        firmware_id: UUID,
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ) -> str:
        """Flash firmware to a device."""
        try:
            # Get device and firmware
            device = await self._device_flashing_use_case._device_repository.find_by_id(device_id)
            if not device:
                raise ValueError(f"Device not found: {device_id}")
            
            firmware = await self._device_flashing_use_case._firmware_repository.find_by_id(firmware_id)
            if not firmware:
                raise ValueError(f"Firmware not found: {firmware_id}")
            
            # Validate compatibility
            if not firmware.is_compatible_with(device.device_type.value):
                raise ValueError(
                    f"Firmware {firmware.name} is not compatible with device type {device.device_type.value}"
                )
            
            # Create progress callback wrapper
            def combined_progress_callback(progress: FlashingProgress) -> None:
                # Track progress
                job_id = f"flash_{device_id}_{firmware_id}"
                self._progress_tracker.update_progress(job_id, progress)
                
                # Call external callback
                if progress_callback:
                    progress_callback(progress)
                
                # Call service callback
                if self._on_flash_progress:
                    self._on_flash_progress(job_id, progress)
            
            # Queue flash job
            job_id = await self._flash_manager.queue_flash_job(
                device=device,
                firmware=firmware,
                progress_callback=combined_progress_callback,
            )
            
            # Notify flash started
            if self._on_flash_started:
                self._on_flash_started(job_id, device, firmware)
            
            logger.info(f"Queued flash job {job_id} for device {device.name}")
            return job_id
        
        except Exception as e:
            logger.error(f"Error flashing device {device_id}: {e}")
            raise
    
    async def flash_device_with_latest_firmware(
        self,
        device_id: UUID,
        firmware_name: Optional[str] = None,
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ) -> str:
        """Flash device with latest compatible firmware."""
        try:
            # Get device
            device = await self._device_flashing_use_case._device_repository.find_by_id(device_id)
            if not device:
                raise ValueError(f"Device not found: {device_id}")
            
            # Get latest compatible firmware
            compatible_firmware = await self._device_flashing_use_case.get_compatible_firmware(device_id)
            
            if firmware_name:
                # Filter by firmware name
                compatible_firmware = [
                    fw for fw in compatible_firmware if fw.name == firmware_name
                ]
            
            if not compatible_firmware:
                raise ValueError(f"No compatible firmware found for device {device.name}")
            
            # Get latest version
            latest_firmware = max(compatible_firmware, key=lambda fw: fw.version)
            
            return await self.flash_device(
                device_id=device_id,
                firmware_id=latest_firmware.id,
                progress_callback=progress_callback,
            )
        
        except Exception as e:
            logger.error(f"Error flashing device with latest firmware: {e}")
            raise
    
    async def cancel_flash_job(self, job_id: str) -> bool:
        """Cancel a flash job."""
        try:
            success = await self._flash_manager.cancel_flash_job(job_id)
            if success:
                logger.info(f"Cancelled flash job: {job_id}")
            return success
        except Exception as e:
            logger.error(f"Error cancelling flash job {job_id}: {e}")
            return False
    
    def get_flash_job_status(self, job_id: str) -> Optional[FlashJob]:
        """Get status of a flash job."""
        return self._flash_manager.get_job_status(job_id)
    
    def get_all_flash_jobs(self) -> Dict[str, FlashJob]:
        """Get all flash jobs."""
        return self._flash_manager.get_all_jobs()
    
    def get_running_flash_jobs(self) -> Dict[str, FlashJob]:
        """Get currently running flash jobs."""
        return self._flash_manager.get_running_jobs()
    
    def get_device_flash_history(self, device_id: UUID) -> List[FlashJob]:
        """Get flash history for a device."""
        all_jobs = self._flash_manager.get_all_jobs()
        return [
            job for job in all_jobs.values()
            if job.device.id == device_id
        ]
    
    async def erase_device(self, device_id: UUID) -> bool:
        """Erase device flash memory."""
        try:
            return await self._device_flashing_use_case.erase_device(device_id)
        except Exception as e:
            logger.error(f"Error erasing device {device_id}: {e}")
            return False
    
    async def verify_device_firmware(
        self, device_id: UUID, firmware_id: UUID
    ) -> bool:
        """Verify firmware on device."""
        try:
            return await self._device_flashing_use_case.verify_device_firmware(
                device_id, firmware_id
            )
        except Exception as e:
            logger.error(f"Error verifying firmware on device {device_id}: {e}")
            return False
    
    async def get_device_info(self, device_id: UUID) -> Dict[str, Any]:
        """Get detailed device information."""
        try:
            return await self._device_flashing_use_case.get_device_info(device_id)
        except Exception as e:
            logger.error(f"Error getting device info for {device_id}: {e}")
            return {}
    
    async def get_compatible_firmware(self, device_id: UUID) -> List[Firmware]:
        """Get list of firmware compatible with device."""
        try:
            return await self._device_flashing_use_case.get_compatible_firmware(device_id)
        except Exception as e:
            logger.error(f"Error getting compatible firmware for device {device_id}: {e}")
            return []
    
    async def get_recommended_firmware(self, device_id: UUID) -> Optional[Firmware]:
        """Get recommended firmware for device."""
        try:
            return await self._device_flashing_use_case.get_recommended_firmware(device_id)
        except Exception as e:
            logger.error(f"Error getting recommended firmware for device {device_id}: {e}")
            return None
    
    def get_flash_statistics(self) -> Dict[str, Any]:
        """Get flash operation statistics."""
        all_jobs = self._flash_manager.get_all_jobs()
        
        stats = {
            "total_jobs": len(all_jobs),
            "completed_jobs": 0,
            "failed_jobs": 0,
            "cancelled_jobs": 0,
            "running_jobs": self._flash_manager.get_running_count(),
            "queued_jobs": self._flash_manager.get_queue_size(),
        }
        
        for job in all_jobs.values():
            if job.status.value == "completed":
                stats["completed_jobs"] += 1
            elif job.status.value == "failed":
                stats["failed_jobs"] += 1
            elif job.status.value == "cancelled":
                stats["cancelled_jobs"] += 1
        
        return stats
    
    def set_flash_started_callback(
        self, callback: Callable[[str, Device, Firmware], None]
    ) -> None:
        """Set callback for when flash operation starts."""
        self._on_flash_started = callback
    
    def set_flash_completed_callback(
        self, callback: Callable[[str, Device, Firmware, bool], None]
    ) -> None:
        """Set callback for when flash operation completes."""
        self._on_flash_completed = callback
    
    def set_flash_progress_callback(
        self, callback: Callable[[str, FlashingProgress], None]
    ) -> None:
        """Set callback for flash progress updates."""
        self._on_flash_progress = callback
    
    def get_progress_tracker(self) -> ProgressTracker:
        """Get the progress tracker instance."""
        return self._progress_tracker