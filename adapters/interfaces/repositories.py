"""Repository interface definitions."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from core.entities.device import Device
from core.entities.firmware import Firmware, FirmwareVersion
from core.entities.configuration import DeviceConfiguration


class DeviceRepositoryInterface(ABC):
    """Interface for device data persistence."""
    
    @abstractmethod
    async def save(self, device: Device) -> Device:
        """Save a device."""
        pass
    
    @abstractmethod
    async def find_by_id(self, device_id: UUID) -> Optional[Device]:
        """Find device by ID."""
        pass
    
    @abstractmethod
    async def find_by_serial_port(self, serial_port: str) -> Optional[Device]:
        """Find device by serial port."""
        pass
    
    @abstractmethod
    async def find_by_mac_address(self, mac_address: str) -> Optional[Device]:
        """Find device by MAC address."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Device]:
        """Find all devices."""
        pass
    
    @abstractmethod
    async def delete(self, device_id: UUID) -> bool:
        """Delete a device."""
        pass
    
    @abstractmethod
    async def find_by_status(self, status: str) -> List[Device]:
        """Find devices by status."""
        pass
    
    @abstractmethod
    async def find_by_device_type(self, device_type: str) -> List[Device]:
        """Find devices by type."""
        pass


class FirmwareRepositoryInterface(ABC):
    """Interface for firmware data persistence."""
    
    @abstractmethod
    async def save(self, firmware: Firmware) -> Firmware:
        """Save firmware metadata."""
        pass
    
    @abstractmethod
    async def find_by_id(self, firmware_id: UUID) -> Optional[Firmware]:
        """Find firmware by ID."""
        pass
    
    @abstractmethod
    async def find_by_name_and_version(
        self, name: str, version: FirmwareVersion
    ) -> Optional[Firmware]:
        """Find firmware by name and version."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Firmware]:
        """Find all firmware."""
        pass
    
    @abstractmethod
    async def find_compatible(self, device_type: str) -> List[Firmware]:
        """Find firmware compatible with device type."""
        pass
    
    @abstractmethod
    async def find_by_name(self, name: str) -> List[Firmware]:
        """Find all firmware versions by name."""
        pass
    
    @abstractmethod
    async def delete(self, firmware_id: UUID) -> bool:
        """Delete firmware."""
        pass


class ConfigurationRepositoryInterface(ABC):
    """Interface for configuration data persistence."""
    
    @abstractmethod
    async def save(self, configuration: DeviceConfiguration) -> DeviceConfiguration:
        """Save configuration."""
        pass
    
    @abstractmethod
    async def find_by_id(self, config_id: UUID) -> Optional[DeviceConfiguration]:
        """Find configuration by ID."""
        pass
    
    @abstractmethod
    async def find_by_device_id(self, device_id: UUID) -> List[DeviceConfiguration]:
        """Find all configurations for a device."""
        pass
    
    @abstractmethod
    async def find_active_by_device_id(
        self, device_id: UUID
    ) -> Optional[DeviceConfiguration]:
        """Find active configuration for a device."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[DeviceConfiguration]:
        """Find all configurations."""
        pass
    
    @abstractmethod
    async def find_by_status(self, status: str) -> List[DeviceConfiguration]:
        """Find configurations by status."""
        pass
    
    @abstractmethod
    async def delete(self, config_id: UUID) -> bool:
        """Delete configuration."""
        pass