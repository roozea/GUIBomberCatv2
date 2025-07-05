"""Configuration domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4


class SecurityMode(Enum):
    """WiFi security modes."""
    OPEN = "open"
    WEP = "wep"
    WPA = "wpa"
    WPA2 = "wpa2"
    WPA3 = "wpa3"


class ConfigurationStatus(Enum):
    """Configuration deployment status."""
    DRAFT = "draft"
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"


@dataclass
class NetworkConfiguration:
    """Network configuration for devices."""
    
    ssid: str
    password: Optional[str]
    security_mode: SecurityMode
    static_ip: Optional[str] = None
    gateway: Optional[str] = None
    subnet_mask: Optional[str] = None
    dns_primary: Optional[str] = None
    dns_secondary: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate network configuration."""
        if not self.ssid:
            return False
        
        if self.security_mode != SecurityMode.OPEN and not self.password:
            return False
        
        # If static IP is set, gateway and subnet should also be set
        if self.static_ip and (not self.gateway or not self.subnet_mask):
            return False
        
        return True
    
    def is_static_ip(self) -> bool:
        """Check if configuration uses static IP."""
        return self.static_ip is not None


@dataclass
class MQTTConfiguration:
    """MQTT broker configuration."""
    
    broker_host: str
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    use_ssl: bool = False
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    keep_alive: int = 60
    qos: int = 1
    
    def validate(self) -> bool:
        """Validate MQTT configuration."""
        if not self.broker_host:
            return False
        
        if self.broker_port <= 0 or self.broker_port > 65535:
            return False
        
        if self.use_ssl and not self.ca_cert_path:
            return False
        
        return True


@dataclass
class DeviceConfiguration:
    """Complete device configuration."""
    
    id: UUID
    device_id: UUID
    name: str
    network: NetworkConfiguration
    mqtt: Optional[MQTTConfiguration]
    custom_settings: Dict[str, Any]
    status: ConfigurationStatus
    version: int
    created_at: datetime
    updated_at: datetime
    applied_at: Optional[datetime] = None
    
    @classmethod
    def create(
        cls,
        device_id: UUID,
        name: str,
        network: NetworkConfiguration,
        mqtt: Optional[MQTTConfiguration] = None,
        custom_settings: Optional[Dict[str, Any]] = None,
    ) -> "DeviceConfiguration":
        """Create a new device configuration."""
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            device_id=device_id,
            name=name,
            network=network,
            mqtt=mqtt,
            custom_settings=custom_settings or {},
            status=ConfigurationStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
        )
    
    def validate(self) -> bool:
        """Validate complete configuration."""
        if not self.network.validate():
            return False
        
        if self.mqtt and not self.mqtt.validate():
            return False
        
        return True
    
    def mark_as_applied(self) -> None:
        """Mark configuration as successfully applied."""
        self.status = ConfigurationStatus.APPLIED
        self.applied_at = datetime.utcnow()
        self.updated_at = self.applied_at
    
    def mark_as_failed(self) -> None:
        """Mark configuration as failed to apply."""
        self.status = ConfigurationStatus.FAILED
        self.updated_at = datetime.utcnow()
    
    def create_new_version(self) -> "DeviceConfiguration":
        """Create a new version of this configuration."""
        new_config = DeviceConfiguration(
            id=uuid4(),
            device_id=self.device_id,
            name=self.name,
            network=self.network,
            mqtt=self.mqtt,
            custom_settings=self.custom_settings.copy(),
            status=ConfigurationStatus.DRAFT,
            version=self.version + 1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        return new_config