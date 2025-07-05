"""Dependency injection for the API layer."""

import logging
from typing import Optional
from dataclasses import dataclass

from core.use_cases.device_management import DeviceManagementUseCase
from core.use_cases.firmware_management import FirmwareManagementUseCase
from core.use_cases.configuration_management import ConfigurationManagementUseCase
from core.use_cases.device_flashing import DeviceFlashingUseCase
from modules.bombercat_flash import FlashService, FlashManager, ProgressTracker
from infrastructure.esptool_adapter import ESPToolAdapter
from infrastructure.aws_iot_adapter import AWSIoTAdapter

# For now, we'll use in-memory implementations
# In a real application, these would be proper database implementations
from api.repositories import (
    InMemoryDeviceRepository,
    InMemoryFirmwareRepository,
    InMemoryConfigurationRepository,
)


logger = logging.getLogger(__name__)


@dataclass
class Dependencies:
    """Container for all application dependencies."""
    # Repositories
    device_repository: InMemoryDeviceRepository
    firmware_repository: InMemoryFirmwareRepository
    configuration_repository: InMemoryConfigurationRepository
    
    # Services
    esptool_adapter: ESPToolAdapter
    aws_iot_adapter: Optional[AWSIoTAdapter]
    
    # Use Cases
    device_management_use_case: DeviceManagementUseCase
    firmware_management_use_case: FirmwareManagementUseCase
    configuration_management_use_case: ConfigurationManagementUseCase
    device_flashing_use_case: DeviceFlashingUseCase
    
    # Flash Module
    flash_manager: FlashManager
    flash_service: FlashService
    progress_tracker: ProgressTracker


_dependencies: Optional[Dependencies] = None


def get_dependencies() -> Dependencies:
    """Get or create application dependencies."""
    global _dependencies
    
    if _dependencies is None:
        _dependencies = _create_dependencies()
    
    return _dependencies


def _create_dependencies() -> Dependencies:
    """Create and wire up all application dependencies."""
    logger.info("Initializing application dependencies")
    
    # Create repositories
    device_repository = InMemoryDeviceRepository()
    firmware_repository = InMemoryFirmwareRepository()
    configuration_repository = InMemoryConfigurationRepository()
    
    # Create infrastructure services
    esptool_adapter = ESPToolAdapter()
    
    # AWS IoT adapter (optional, requires configuration)
    aws_iot_adapter = None
    try:
        aws_iot_adapter = AWSIoTAdapter(
            region="us-east-1",  # Configure as needed
            # Add other AWS configuration as needed
        )
        logger.info("AWS IoT adapter initialized")
    except Exception as e:
        logger.warning(f"AWS IoT adapter not available: {e}")
    
    # Create use cases
    device_management_use_case = DeviceManagementUseCase(
        device_repository=device_repository,
        discovery_service=esptool_adapter,
    )
    
    firmware_management_use_case = FirmwareManagementUseCase(
        firmware_repository=firmware_repository,
        storage_service=None,  # Could implement file system storage
    )
    
    configuration_management_use_case = ConfigurationManagementUseCase(
        configuration_repository=configuration_repository,
        deployment_service=aws_iot_adapter,
    )
    
    device_flashing_use_case = DeviceFlashingUseCase(
        device_repository=device_repository,
        firmware_repository=firmware_repository,
        flashing_service=esptool_adapter,
    )
    
    # Create flash module components
    progress_tracker = ProgressTracker()
    flash_manager = FlashManager()
    
    flash_service = FlashService(
        device_flashing_use_case=device_flashing_use_case,
        flash_manager=flash_manager,
        progress_tracker=progress_tracker,
    )
    
    dependencies = Dependencies(
        device_repository=device_repository,
        firmware_repository=firmware_repository,
        configuration_repository=configuration_repository,
        esptool_adapter=esptool_adapter,
        aws_iot_adapter=aws_iot_adapter,
        device_management_use_case=device_management_use_case,
        firmware_management_use_case=firmware_management_use_case,
        configuration_management_use_case=configuration_management_use_case,
        device_flashing_use_case=device_flashing_use_case,
        flash_manager=flash_manager,
        flash_service=flash_service,
        progress_tracker=progress_tracker,
    )
    
    logger.info("Application dependencies initialized successfully")
    return dependencies


# FastAPI dependency functions
def get_device_management_use_case() -> DeviceManagementUseCase:
    """Get device management use case."""
    return get_dependencies().device_management_use_case


def get_firmware_management_use_case() -> FirmwareManagementUseCase:
    """Get firmware management use case."""
    return get_dependencies().firmware_management_use_case


def get_configuration_management_use_case() -> ConfigurationManagementUseCase:
    """Get configuration management use case."""
    return get_dependencies().configuration_management_use_case


def get_device_flashing_use_case() -> DeviceFlashingUseCase:
    """Get device flashing use case."""
    return get_dependencies().device_flashing_use_case


def get_flash_service() -> FlashService:
    """Get flash service."""
    return get_dependencies().flash_service


def get_progress_tracker() -> ProgressTracker:
    """Get progress tracker."""
    return get_dependencies().progress_tracker


def get_serial_port():
    """Get serial port for device communication.
    
    This is a mock implementation for testing purposes.
    In a real application, this would return an actual serial port.
    """
    import serial
    # Return a mock serial port for testing
    # In production, this would detect and return the actual device port
    return serial.Serial('/dev/null', 115200, timeout=1)


# Additional service dependencies for API routes
def get_config_service():
    """Get configuration service."""
    return get_dependencies().configuration_management_use_case


def get_relay_service():
    """Get relay service.
    
    Mock implementation - in production this would return actual relay service.
    """
    from adapters.interfaces import RelayServiceInterface
    
    class MockRelayService(RelayServiceInterface):
        async def list_relays(self):
            return []
        
        async def get_status(self, relay_id: str):
            return {"relay_id": relay_id, "state": "off", "last_update": "2024-01-01T00:00:00Z"}
        
        async def get_all_status(self):
            return []
        
        async def control_relay(self, relay_id: str, action: str, duration=None):
            return {"success": True, "action": action}
        
        async def get_metrics(self, relay_id: str, hours: int):
            return {"relay_id": relay_id, "metrics": []}
        
        async def emergency_stop(self):
            return {"stopped_relays": [], "timestamp": "2024-01-01T00:00:00Z"}
        
        async def get_schedules(self, relay_id: str):
            return []
        
        async def create_schedule(self, relay_id: str, schedule_data):
            return "schedule_123"
    
    return MockRelayService()


def get_mqtt_service():
    """Get MQTT service.
    
    Mock implementation - in production this would return actual MQTT service.
    """
    from adapters.interfaces import MQTTServiceInterface
    
    class MockMQTTService(MQTTServiceInterface):
        async def get_connection_status(self):
            return {
                "broker_host": "localhost",
                "broker_port": 1883,
                "client_id": "bombercat",
                "connected": False
            }
        
        async def connect(self):
            return {"connected": True, "broker": "localhost:1883"}
        
        async def disconnect(self):
            return True
        
        async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
            return {"message_id": "msg_123"}
        
        async def subscribe(self, topic: str, qos: int = 0, callback_url=None):
            return {"subscription_id": "sub_123"}
        
        async def unsubscribe(self, topic: str):
            return True
        
        async def list_subscriptions(self):
            return []
        
        async def get_topic_messages(self, topic: str, limit: int = 100):
            return []
        
        async def discover_topics(self, pattern=None):
            return []
        
        async def get_metrics(self):
            return {"messages_sent": 0, "messages_received": 0}
        
        async def update_config(self, config):
            return {"config": config, "restart_required": False}
        
        async def get_config(self):
            return {"broker_host": "localhost", "broker_port": 1883}
        
        async def test_connection(self, broker_config=None):
            return {"connected": True, "latency_ms": 10}
    
    return MockMQTTService()


def get_device_service():
    """Get device service."""
    return get_dependencies().device_management_use_case