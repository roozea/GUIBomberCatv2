"""BomberCat Flash Module.

This module provides firmware flashing capabilities for BomberCat devices,
including ESP32, ESP8266, and other supported microcontrollers.
"""

from modules.bombercat_flash.flash_manager import FlashManager
from modules.bombercat_flash.flash_service import FlashService
from modules.bombercat_flash.progress_tracker import ProgressTracker

__version__ = "0.1.0"

__all__ = [
    "FlashManager",
    "FlashService",
    "ProgressTracker",
]