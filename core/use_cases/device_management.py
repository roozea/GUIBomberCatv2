"""Device management use cases."""

from typing import List, Optional
from uuid import UUID

from core.entities.device import Device, DeviceType, DeviceStatus


class DeviceRepository:
    """Abstract repository interface for device persistence."""
    
    async def save(self, device: Device) -> Device:
        """Save a device."""
        raise NotImplementedError
    
    async def find_by_id(self, device_id: UUID) -> Optional[Device]:
        """Find device by ID."""
        raise NotImplementedError
    
    async def find_by_serial_port(self, serial_port: str) -> Optional[Device]:
        """Find device by serial port."""
        raise NotImplementedError
    
    async def find_by_mac_address(self, mac_address: str) -> Optional[Device]:
        """Find device by MAC address."""
        raise NotImplementedError
    
    async def find_all(self) -> List[Device]:
        """Find all devices."""
        raise NotImplementedError
    
    async def delete(self, device_id: UUID) -> bool:
        """Delete a device."""
        raise NotImplementedError


class DeviceDiscoveryService:
    """Abstract service interface for device discovery."""
    
    async def scan_serial_ports(self) -> List[str]:
        """Scan for available serial ports."""
        raise NotImplementedError
    
    async def scan_network_devices(self) -> List[dict]:
        """Scan for network-connected devices."""
        raise NotImplementedError
    
    async def identify_device_type(self, serial_port: str) -> Optional[DeviceType]:
        """Identify device type from serial port."""
        raise NotImplementedError


class DeviceManagementUseCase:
    """Use case for managing BomberCat devices."""
    
    def __init__(
        self,
        device_repository: DeviceRepository,
        discovery_service: DeviceDiscoveryService,
    ):
        self._device_repository = device_repository
        self._discovery_service = discovery_service
    
    async def register_device(
        self,
        name: str,
        device_type: DeviceType,
        serial_port: Optional[str] = None,
        mac_address: Optional[str] = None,
    ) -> Device:
        """Register a new device."""
        # Check if device already exists
        if serial_port:
            existing = await self._device_repository.find_by_serial_port(serial_port)
            if existing:
                raise ValueError(f"Device with serial port {serial_port} already exists")
        
        if mac_address:
            existing = await self._device_repository.find_by_mac_address(mac_address)
            if existing:
                raise ValueError(f"Device with MAC address {mac_address} already exists")
        
        # Create and save new device
        device = Device.create(
            name=name,
            device_type=device_type,
            serial_port=serial_port,
            mac_address=mac_address,
        )
        
        return await self._device_repository.save(device)
    
    async def get_device(self, device_id: UUID) -> Optional[Device]:
        """Get device by ID."""
        return await self._device_repository.find_by_id(device_id)
    
    async def list_devices(self) -> List[Device]:
        """List all registered devices."""
        return await self._device_repository.find_all()
    
    async def update_device_status(
        self,
        device_id: UUID,
        status: DeviceStatus,
    ) -> Optional[Device]:
        """Update device status."""
        device = await self._device_repository.find_by_id(device_id)
        if not device:
            return None
        
        device.update_status(status)
        return await self._device_repository.save(device)
    
    async def update_device_network_info(
        self,
        device_id: UUID,
        ip_address: str,
        mac_address: Optional[str] = None,
    ) -> Optional[Device]:
        """Update device network information."""
        device = await self._device_repository.find_by_id(device_id)
        if not device:
            return None
        
        device.update_network_info(ip_address, mac_address)
        return await self._device_repository.save(device)
    
    async def discover_devices(self) -> List[dict]:
        """Discover available devices."""
        discovered_devices = []
        
        # Scan serial ports
        serial_ports = await self._discovery_service.scan_serial_ports()
        for port in serial_ports:
            device_type = await self._discovery_service.identify_device_type(port)
            discovered_devices.append({
                "type": "serial",
                "port": port,
                "device_type": device_type,
                "registered": await self._is_device_registered(serial_port=port),
            })
        
        # Scan network devices
        network_devices = await self._discovery_service.scan_network_devices()
        for device_info in network_devices:
            discovered_devices.append({
                "type": "network",
                "ip_address": device_info.get("ip_address"),
                "mac_address": device_info.get("mac_address"),
                "device_type": device_info.get("device_type"),
                "registered": await self._is_device_registered(
                    mac_address=device_info.get("mac_address")
                ),
            })
        
        return discovered_devices
    
    async def remove_device(self, device_id: UUID) -> bool:
        """Remove a device."""
        return await self._device_repository.delete(device_id)
    
    async def _is_device_registered(
        self,
        serial_port: Optional[str] = None,
        mac_address: Optional[str] = None,
    ) -> bool:
        """Check if device is already registered."""
        if serial_port:
            device = await self._device_repository.find_by_serial_port(serial_port)
            if device:
                return True
        
        if mac_address:
            device = await self._device_repository.find_by_mac_address(mac_address)
            if device:
                return True
        
        return False