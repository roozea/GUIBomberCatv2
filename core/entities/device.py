"""Device domain entity."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4


class DeviceType(Enum):
    """Types of BomberCat devices."""
    ESP32 = "esp32"
    ESP8266 = "esp8266"
    ARDUINO = "arduino"
    RASPBERRY_PI = "raspberry_pi"


class DeviceStatus(Enum):
    """Device connection and operational status."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    FLASHING = "flashing"
    CONFIGURING = "configuring"
    READY = "ready"
    ERROR = "error"


@dataclass
class Device:
    """Core device entity representing a BomberCat IoT device."""
    
    id: UUID
    name: str
    device_type: DeviceType
    serial_port: Optional[str]
    mac_address: Optional[str]
    ip_address: Optional[str]
    status: DeviceStatus
    firmware_version: Optional[str]
    last_seen: Optional[datetime]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def create(
        cls,
        name: str,
        device_type: DeviceType,
        serial_port: Optional[str] = None,
        mac_address: Optional[str] = None,
    ) -> "Device":
        """Create a new device instance."""
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            name=name,
            device_type=device_type,
            serial_port=serial_port,
            mac_address=mac_address,
            ip_address=None,
            status=DeviceStatus.DISCONNECTED,
            firmware_version=None,
            last_seen=None,
            metadata={},
            created_at=now,
            updated_at=now,
        )
    
    def update_status(self, status: DeviceStatus) -> None:
        """Update device status and timestamp."""
        self.status = status
        self.updated_at = datetime.utcnow()
        if status in [DeviceStatus.CONNECTED, DeviceStatus.READY]:
            self.last_seen = self.updated_at
    
    def update_network_info(self, ip_address: str, mac_address: Optional[str] = None) -> None:
        """Update device network information."""
        self.ip_address = ip_address
        if mac_address:
            self.mac_address = mac_address
        self.updated_at = datetime.utcnow()
    
    def update_firmware(self, version: str) -> None:
        """Update device firmware version."""
        self.firmware_version = version
        self.updated_at = datetime.utcnow()
    
    def is_online(self) -> bool:
        """Check if device is currently online."""
        return self.status in [DeviceStatus.CONNECTED, DeviceStatus.READY]
    
    def can_flash(self) -> bool:
        """Check if device can be flashed."""
        return self.status in [
            DeviceStatus.CONNECTED,
            DeviceStatus.READY,
            DeviceStatus.DISCONNECTED
        ] and self.serial_port is not None