"""In-memory repository implementations for development and testing."""

import logging
from typing import Dict, List, Optional
from uuid import UUID
from threading import Lock

from core.entities.device import Device
from core.entities.firmware import Firmware
from core.entities.configuration import DeviceConfiguration
from adapters.interfaces.repositories import (
    DeviceRepositoryInterface,
    FirmwareRepositoryInterface,
    ConfigurationRepositoryInterface,
)


logger = logging.getLogger(__name__)


class InMemoryDeviceRepository(DeviceRepositoryInterface):
    """In-memory implementation of device repository."""
    
    def __init__(self):
        self._devices: Dict[UUID, Device] = {}
        self._lock = Lock()
    
    async def save(self, device: Device) -> Device:
        """Save a device."""
        with self._lock:
            self._devices[device.id] = device
            logger.debug(f"Saved device: {device.name} ({device.id})")
            return device
    
    async def find_by_id(self, device_id: UUID) -> Optional[Device]:
        """Find device by ID."""
        with self._lock:
            return self._devices.get(device_id)
    
    async def find_by_name(self, name: str) -> Optional[Device]:
        """Find device by name."""
        with self._lock:
            for device in self._devices.values():
                if device.name == name:
                    return device
            return None
    
    async def find_by_serial_port(self, serial_port: str) -> Optional[Device]:
        """Find device by serial port."""
        with self._lock:
            for device in self._devices.values():
                if device.network_info and device.network_info.get("serial_port") == serial_port:
                    return device
            return None
    
    async def find_by_mac_address(self, mac_address: str) -> Optional[Device]:
        """Find device by MAC address."""
        with self._lock:
            for device in self._devices.values():
                if device.network_info and device.network_info.get("mac_address") == mac_address:
                    return device
            return None
    
    async def find_all(self) -> List[Device]:
        """Find all devices."""
        with self._lock:
            return list(self._devices.values())
    
    async def find_by_device_type(self, device_type: str) -> List[Device]:
        """Find devices by type."""
        with self._lock:
            return [
                device for device in self._devices.values()
                if device.device_type.value == device_type
            ]
    
    async def find_by_status(self, status: str) -> List[Device]:
        """Find devices by status."""
        with self._lock:
            return [
                device for device in self._devices.values()
                if device.status.value == status
            ]
    
    async def delete(self, device_id: UUID) -> bool:
        """Delete a device."""
        with self._lock:
            if device_id in self._devices:
                device = self._devices.pop(device_id)
                logger.debug(f"Deleted device: {device.name} ({device_id})")
                return True
            return False
    
    async def exists(self, device_id: UUID) -> bool:
        """Check if device exists."""
        with self._lock:
            return device_id in self._devices
    
    async def count(self) -> int:
        """Get total device count."""
        with self._lock:
            return len(self._devices)


class InMemoryFirmwareRepository(FirmwareRepositoryInterface):
    """In-memory implementation of firmware repository."""
    
    def __init__(self):
        self._firmware: Dict[UUID, Firmware] = {}
        self._lock = Lock()
    
    async def save(self, firmware: Firmware) -> Firmware:
        """Save firmware."""
        with self._lock:
            self._firmware[firmware.id] = firmware
            logger.debug(f"Saved firmware: {firmware.name} v{firmware.version} ({firmware.id})")
            return firmware
    
    async def find_by_id(self, firmware_id: UUID) -> Optional[Firmware]:
        """Find firmware by ID."""
        with self._lock:
            return self._firmware.get(firmware_id)
    
    async def find_by_name(self, name: str) -> List[Firmware]:
        """Find firmware by name."""
        with self._lock:
            return [
                firmware for firmware in self._firmware.values()
                if firmware.name == name
            ]
    
    async def find_by_name_and_version(self, name: str, version: str) -> Optional[Firmware]:
        """Find firmware by name and version."""
        with self._lock:
            for firmware in self._firmware.values():
                if firmware.name == name and str(firmware.version) == version:
                    return firmware
            return None
    
    async def find_all(self) -> List[Firmware]:
        """Find all firmware."""
        with self._lock:
            return list(self._firmware.values())
    
    async def find_by_device_type(self, device_type: str) -> List[Firmware]:
        """Find firmware compatible with device type."""
        with self._lock:
            return [
                firmware for firmware in self._firmware.values()
                if firmware.is_compatible_with(device_type)
            ]
    
    async def find_compatible(self, device_type: str) -> List[Firmware]:
        """Find firmware compatible with device type."""
        return await self.find_by_device_type(device_type)
    
    async def find_latest_by_name(self, name: str) -> Optional[Firmware]:
        """Find latest version of firmware by name."""
        firmware_list = await self.find_by_name(name)
        if not firmware_list:
            return None
        return max(firmware_list, key=lambda fw: fw.version)
    
    async def find_latest_by_device_type(self, device_type: str) -> List[Firmware]:
        """Find latest firmware versions for device type."""
        compatible_firmware = await self.find_by_device_type(device_type)
        
        # Group by name and get latest version for each
        firmware_by_name: Dict[str, Firmware] = {}
        for firmware in compatible_firmware:
            if (
                firmware.name not in firmware_by_name or
                firmware.version > firmware_by_name[firmware.name].version
            ):
                firmware_by_name[firmware.name] = firmware
        
        return list(firmware_by_name.values())
    
    async def delete(self, firmware_id: UUID) -> bool:
        """Delete firmware."""
        with self._lock:
            if firmware_id in self._firmware:
                firmware = self._firmware.pop(firmware_id)
                logger.debug(f"Deleted firmware: {firmware.name} v{firmware.version} ({firmware_id})")
                return True
            return False
    
    async def exists(self, firmware_id: UUID) -> bool:
        """Check if firmware exists."""
        with self._lock:
            return firmware_id in self._firmware
    
    async def count(self) -> int:
        """Get total firmware count."""
        with self._lock:
            return len(self._firmware)


class InMemoryConfigurationRepository(ConfigurationRepositoryInterface):
    """In-memory implementation of configuration repository."""
    
    def __init__(self):
        self._configurations: Dict[UUID, DeviceConfiguration] = {}
        self._device_configurations: Dict[UUID, UUID] = {}  # device_id -> config_id
        self._lock = Lock()
    
    async def save(self, configuration: DeviceConfiguration) -> DeviceConfiguration:
        """Save configuration."""
        with self._lock:
            self._configurations[configuration.id] = configuration
            logger.debug(f"Saved configuration: {configuration.name} ({configuration.id})")
            return configuration
    
    async def find_by_id(self, config_id: UUID) -> Optional[DeviceConfiguration]:
        """Find configuration by ID."""
        with self._lock:
            return self._configurations.get(config_id)
    
    async def find_by_name(self, name: str) -> Optional[DeviceConfiguration]:
        """Find configuration by name."""
        with self._lock:
            for config in self._configurations.values():
                if config.name == name:
                    return config
            return None
    
    async def find_by_device_id(self, device_id: UUID) -> List[DeviceConfiguration]:
        """Find all configurations for a device."""
        with self._lock:
            config_id = self._device_configurations.get(device_id)
            if config_id and config_id in self._configurations:
                return [self._configurations[config_id]]
            return []
    
    async def find_active_by_device_id(self, device_id: UUID) -> Optional[DeviceConfiguration]:
        """Find active configuration for a device."""
        with self._lock:
            config_id = self._device_configurations.get(device_id)
            if config_id:
                return self._configurations.get(config_id)
            return None
    
    async def find_all(self) -> List[DeviceConfiguration]:
        """Find all configurations."""
        with self._lock:
            return list(self._configurations.values())
    
    async def find_by_status(self, status: str) -> List[DeviceConfiguration]:
        """Find configurations by status."""
        with self._lock:
            return [
                config for config in self._configurations.values()
                if config.status.value == status
            ]
    
    async def assign_to_device(self, device_id: UUID, config_id: UUID) -> bool:
        """Assign configuration to device."""
        with self._lock:
            if config_id in self._configurations:
                self._device_configurations[device_id] = config_id
                logger.debug(f"Assigned configuration {config_id} to device {device_id}")
                return True
            return False
    
    async def unassign_from_device(self, device_id: UUID) -> bool:
        """Unassign configuration from device."""
        with self._lock:
            if device_id in self._device_configurations:
                config_id = self._device_configurations.pop(device_id)
                logger.debug(f"Unassigned configuration {config_id} from device {device_id}")
                return True
            return False
    
    async def delete(self, config_id: UUID) -> bool:
        """Delete configuration."""
        with self._lock:
            if config_id in self._configurations:
                config = self._configurations.pop(config_id)
                
                # Remove device assignments
                devices_to_unassign = [
                    device_id for device_id, assigned_config_id in self._device_configurations.items()
                    if assigned_config_id == config_id
                ]
                for device_id in devices_to_unassign:
                    del self._device_configurations[device_id]
                
                logger.debug(f"Deleted configuration: {config.name} ({config_id})")
                return True
            return False
    
    async def exists(self, config_id: UUID) -> bool:
        """Check if configuration exists."""
        with self._lock:
            return config_id in self._configurations
    
    async def count(self) -> int:
        """Get total configuration count."""
        with self._lock:
            return len(self._configurations)