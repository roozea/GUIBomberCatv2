"""Service interface definitions."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Callable, Any

from core.entities.device import Device, DeviceType
from core.entities.firmware import Firmware
from core.entities.configuration import DeviceConfiguration, NetworkConfiguration, MQTTConfiguration
from core.use_cases.device_flashing import FlashingProgress


class DeviceDiscoveryServiceInterface(ABC):
    """Interface for device discovery operations."""
    
    @abstractmethod
    async def scan_serial_ports(self) -> List[str]:
        """Scan for available serial ports."""
        pass
    
    @abstractmethod
    async def scan_network_devices(self) -> List[dict]:
        """Scan for network-connected devices."""
        pass
    
    @abstractmethod
    async def identify_device_type(self, serial_port: str) -> Optional[DeviceType]:
        """Identify device type from serial port."""
        pass
    
    @abstractmethod
    async def get_device_info(self, serial_port: str) -> dict:
        """Get detailed device information from serial port."""
        pass
    
    @abstractmethod
    async def ping_device(self, ip_address: str) -> bool:
        """Ping device at IP address."""
        pass


class FlashingServiceInterface(ABC):
    """Interface for device flashing operations."""
    
    @abstractmethod
    async def flash_firmware(
        self,
        device: Device,
        firmware: Firmware,
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ) -> bool:
        """Flash firmware to device."""
        pass
    
    @abstractmethod
    async def erase_device(self, device: Device) -> bool:
        """Erase device flash memory."""
        pass
    
    @abstractmethod
    async def verify_firmware(self, device: Device, firmware: Firmware) -> bool:
        """Verify firmware on device matches expected firmware."""
        pass
    
    @abstractmethod
    async def read_device_info(self, device: Device) -> dict:
        """Read device information (chip type, flash size, etc.)."""
        pass
    
    @abstractmethod
    async def check_connection(self, device: Device) -> bool:
        """Check if device is connected and responsive."""
        pass
    
    @abstractmethod
    async def reset_device(self, device: Device) -> bool:
        """Reset device."""
        pass


class ConfigurationDeploymentServiceInterface(ABC):
    """Interface for deploying configurations to devices."""
    
    @abstractmethod
    async def deploy_configuration(
        self, device: Device, configuration: DeviceConfiguration
    ) -> bool:
        """Deploy configuration to device."""
        pass
    
    @abstractmethod
    async def validate_network_settings(
        self, network_config: NetworkConfiguration
    ) -> bool:
        """Validate network configuration settings."""
        pass
    
    @abstractmethod
    async def test_mqtt_connection(self, mqtt_config: MQTTConfiguration) -> bool:
        """Test MQTT connection with given configuration."""
        pass
    
    @abstractmethod
    async def backup_device_configuration(self, device: Device) -> dict:
        """Backup current device configuration."""
        pass
    
    @abstractmethod
    async def restore_device_configuration(
        self, device: Device, backup_data: dict
    ) -> bool:
        """Restore device configuration from backup."""
        pass


class FirmwareStorageServiceInterface(ABC):
    """Interface for firmware file storage operations."""
    
    @abstractmethod
    async def store_firmware_file(
        self, file_path: Path, content: bytes
    ) -> tuple[int, str]:
        """Store firmware file and return size and checksum."""
        pass
    
    @abstractmethod
    async def delete_firmware_file(self, file_path: Path) -> bool:
        """Delete firmware file."""
        pass
    
    @abstractmethod
    async def get_firmware_file(self, file_path: Path) -> Optional[bytes]:
        """Get firmware file content."""
        pass
    
    @abstractmethod
    async def verify_firmware_file(self, file_path: Path, checksum: str) -> bool:
        """Verify firmware file integrity."""
        pass
    
    @abstractmethod
    async def get_file_info(self, file_path: Path) -> dict:
        """Get file information (size, modified date, etc.)."""
        pass
    
    @abstractmethod
    async def list_firmware_files(self) -> List[Path]:
        """List all stored firmware files."""
        pass


class NotificationServiceInterface(ABC):
    """Interface for sending notifications."""
    
    @abstractmethod
    async def send_device_status_notification(
        self, device: Device, old_status: str, new_status: str
    ) -> bool:
        """Send device status change notification."""
        pass
    
    @abstractmethod
    async def send_flashing_notification(
        self, device: Device, success: bool, error: Optional[str] = None
    ) -> bool:
        """Send firmware flashing completion notification."""
        pass
    
    @abstractmethod
    async def send_configuration_notification(
        self, device: Device, configuration: DeviceConfiguration, success: bool
    ) -> bool:
        """Send configuration deployment notification."""
        pass


class LoggingServiceInterface(ABC):
    """Interface for logging operations."""
    
    @abstractmethod
    async def log_device_operation(
        self, device_id: str, operation: str, details: dict
    ) -> None:
        """Log device operation."""
        pass
    
    @abstractmethod
    async def log_firmware_operation(
        self, firmware_id: str, operation: str, details: dict
    ) -> None:
        """Log firmware operation."""
        pass
    
    @abstractmethod
    async def log_configuration_operation(
        self, config_id: str, operation: str, details: dict
    ) -> None:
        """Log configuration operation."""
        pass
    
    @abstractmethod
    async def get_operation_logs(
        self, entity_type: str, entity_id: str, limit: int = 100
    ) -> List[dict]:
        """Get operation logs for entity."""
        pass