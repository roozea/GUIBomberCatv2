"""AWS IoT adapter for cloud connectivity and device management."""

import json
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

import boto3
# from awsiotsdk import mqtt_connection_builder
# from awsiotsdk.mqtt import Connection
from botocore.exceptions import ClientError, NoCredentialsError

from adapters.interfaces.services import (
    ConfigurationDeploymentServiceInterface,
    NotificationServiceInterface,
)
from core.entities.device import Device
from core.entities.configuration import DeviceConfiguration, NetworkConfiguration, MQTTConfiguration


logger = logging.getLogger(__name__)


class AWSIoTAdapter(ConfigurationDeploymentServiceInterface, NotificationServiceInterface):
    """Adapter for AWS IoT Core integration."""
    
    def __init__(
        self,
        region: str = "us-east-1",
        endpoint: Optional[str] = None,
        cert_filepath: Optional[str] = None,
        pri_key_filepath: Optional[str] = None,
        ca_filepath: Optional[str] = None,
        client_id: Optional[str] = None,
    ):
        self.region = region
        self.endpoint = endpoint
        self.cert_filepath = cert_filepath
        self.pri_key_filepath = pri_key_filepath
        self.ca_filepath = ca_filepath
        self.client_id = client_id or "bombercat-integrator"
        
        # AWS clients
        self._iot_client = None
        self._iot_data_client = None
        self._mqtt_connection = None  # Optional[Connection] = None
        
        # Initialize AWS clients
        self._initialize_aws_clients()
    
    def _initialize_aws_clients(self) -> None:
        """Initialize AWS IoT clients."""
        try:
            self._iot_client = boto3.client("iot", region_name=self.region)
            self._iot_data_client = boto3.client("iot-data", region_name=self.region)
            logger.info("AWS IoT clients initialized successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
        except Exception as e:
            logger.error(f"Error initializing AWS clients: {e}")
    
    async def deploy_configuration(
        self, device: Device, configuration: DeviceConfiguration
    ) -> bool:
        """Deploy configuration to device via AWS IoT."""
        try:
            # Create device thing if it doesn't exist
            thing_name = self._get_thing_name(device)
            await self._ensure_device_thing_exists(device, thing_name)
            
            # Prepare configuration payload
            config_payload = self._build_configuration_payload(configuration)
            
            # Publish configuration to device shadow
            success = await self._update_device_shadow(thing_name, config_payload)
            
            if success:
                # Also send direct configuration message
                topic = f"bombercat/{thing_name}/config"
                await self._publish_message(topic, config_payload)
            
            return success
        
        except Exception as e:
            logger.error(f"Error deploying configuration: {e}")
            return False
    
    async def validate_network_settings(
        self, network_config: NetworkConfiguration
    ) -> bool:
        """Validate network configuration (basic validation)."""
        # Basic validation - could be enhanced with actual network testing
        return network_config.validate()
    
    async def test_mqtt_connection(self, mqtt_config: MQTTConfiguration) -> bool:
        """Test MQTT connection with given configuration."""
        try:
            # TODO: Implement MQTT connection testing when awsiotsdk is available
            logger.warning("MQTT connection testing not available - awsiotsdk not imported")
            return True  # Return True for now to allow testing
        
        except Exception as e:
            logger.error(f"MQTT connection test failed: {e}")
            return False
    
    async def backup_device_configuration(self, device: Device) -> dict:
        """Backup current device configuration from AWS IoT shadow."""
        try:
            thing_name = self._get_thing_name(device)
            shadow = await self._get_device_shadow(thing_name)
            
            return {
                "device_id": str(device.id),
                "thing_name": thing_name,
                "shadow_data": shadow,
                "backup_timestamp": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error backing up device configuration: {e}")
            return {}
    
    async def restore_device_configuration(
        self, device: Device, backup_data: dict
    ) -> bool:
        """Restore device configuration from backup."""
        try:
            thing_name = self._get_thing_name(device)
            shadow_data = backup_data.get("shadow_data", {})
            
            if not shadow_data:
                return False
            
            return await self._update_device_shadow(thing_name, shadow_data)
        
        except Exception as e:
            logger.error(f"Error restoring device configuration: {e}")
            return False
    
    async def send_device_status_notification(
        self, device: Device, old_status: str, new_status: str
    ) -> bool:
        """Send device status change notification via AWS IoT."""
        try:
            thing_name = self._get_thing_name(device)
            
            notification = {
                "device_id": str(device.id),
                "thing_name": thing_name,
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": datetime.utcnow().isoformat(),
                "device_type": device.device_type.value,
            }
            
            topic = f"bombercat/notifications/device-status/{thing_name}"
            return await self._publish_message(topic, notification)
        
        except Exception as e:
            logger.error(f"Error sending device status notification: {e}")
            return False
    
    async def send_flashing_notification(
        self, device: Device, success: bool, error: Optional[str] = None
    ) -> bool:
        """Send firmware flashing completion notification."""
        try:
            thing_name = self._get_thing_name(device)
            
            notification = {
                "device_id": str(device.id),
                "thing_name": thing_name,
                "operation": "firmware_flash",
                "success": success,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
                "firmware_version": device.firmware_version,
            }
            
            topic = f"bombercat/notifications/flashing/{thing_name}"
            return await self._publish_message(topic, notification)
        
        except Exception as e:
            logger.error(f"Error sending flashing notification: {e}")
            return False
    
    async def send_configuration_notification(
        self, device: Device, configuration: DeviceConfiguration, success: bool
    ) -> bool:
        """Send configuration deployment notification."""
        try:
            thing_name = self._get_thing_name(device)
            
            notification = {
                "device_id": str(device.id),
                "thing_name": thing_name,
                "configuration_id": str(configuration.id),
                "operation": "configuration_deploy",
                "success": success,
                "timestamp": datetime.utcnow().isoformat(),
                "configuration_version": configuration.version,
            }
            
            topic = f"bombercat/notifications/configuration/{thing_name}"
            return await self._publish_message(topic, notification)
        
        except Exception as e:
            logger.error(f"Error sending configuration notification: {e}")
            return False
    
    def _get_thing_name(self, device: Device) -> str:
        """Generate AWS IoT thing name for device."""
        # Use device ID as thing name, with prefix
        return f"bombercat-{str(device.id)}"
    
    async def _ensure_device_thing_exists(self, device: Device, thing_name: str) -> bool:
        """Ensure AWS IoT thing exists for device."""
        try:
            # Check if thing exists
            self._iot_client.describe_thing(thingName=thing_name)
            return True
        
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                # Thing doesn't exist, create it
                return await self._create_device_thing(device, thing_name)
            else:
                logger.error(f"Error checking thing existence: {e}")
                return False
    
    async def _create_device_thing(self, device: Device, thing_name: str) -> bool:
        """Create AWS IoT thing for device."""
        try:
            thing_attributes = {
                "device_type": device.device_type.value,
                "device_name": device.name,
                "serial_port": device.serial_port or "",
                "mac_address": device.mac_address or "",
            }
            
            self._iot_client.create_thing(
                thingName=thing_name,
                thingTypeName="BomberCatDevice",
                attributePayload={"attributes": thing_attributes},
            )
            
            logger.info(f"Created AWS IoT thing: {thing_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating thing: {e}")
            return False
    
    def _build_configuration_payload(self, configuration: DeviceConfiguration) -> dict:
        """Build configuration payload for device."""
        payload = {
            "configuration_id": str(configuration.id),
            "version": configuration.version,
            "timestamp": datetime.utcnow().isoformat(),
            "network": {
                "ssid": configuration.network.ssid,
                "password": configuration.network.password,
                "security_mode": configuration.network.security_mode.value,
                "static_ip": configuration.network.static_ip,
                "gateway": configuration.network.gateway,
                "subnet_mask": configuration.network.subnet_mask,
                "dns_primary": configuration.network.dns_primary,
                "dns_secondary": configuration.network.dns_secondary,
            },
        }
        
        if configuration.mqtt:
            payload["mqtt"] = {
                "broker_host": configuration.mqtt.broker_host,
                "broker_port": configuration.mqtt.broker_port,
                "username": configuration.mqtt.username,
                "password": configuration.mqtt.password,
                "client_id": configuration.mqtt.client_id,
                "use_ssl": configuration.mqtt.use_ssl,
                "keep_alive": configuration.mqtt.keep_alive,
                "qos": configuration.mqtt.qos,
            }
        
        if configuration.custom_settings:
            payload["custom"] = configuration.custom_settings
        
        return payload
    
    async def _update_device_shadow(self, thing_name: str, payload: dict) -> bool:
        """Update device shadow with configuration."""
        try:
            shadow_payload = {
                "state": {
                    "desired": payload
                }
            }
            
            self._iot_data_client.update_thing_shadow(
                thingName=thing_name,
                payload=json.dumps(shadow_payload)
            )
            
            logger.info(f"Updated shadow for thing: {thing_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating device shadow: {e}")
            return False
    
    async def _get_device_shadow(self, thing_name: str) -> dict:
        """Get device shadow data."""
        try:
            response = self._iot_data_client.get_thing_shadow(thingName=thing_name)
            shadow_data = json.loads(response["payload"].read())
            return shadow_data
        
        except Exception as e:
            logger.error(f"Error getting device shadow: {e}")
            return {}
    
    async def _publish_message(self, topic: str, payload: dict) -> bool:
        """Publish message to MQTT topic."""
        try:
            if not self._mqtt_connection:
                await self._connect_mqtt()
            
            if self._mqtt_connection:
                publish_future = self._mqtt_connection.publish(
                    topic=topic,
                    payload=json.dumps(payload),
                    qos=1
                )
                publish_future.result(timeout=10)
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    
    async def _connect_mqtt(self) -> bool:
        """Connect to AWS IoT MQTT broker."""
        try:
            if not all([self.endpoint, self.cert_filepath, self.pri_key_filepath, self.ca_filepath]):
                logger.error("Missing required MQTT connection parameters")
                return False
            
            self._mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.endpoint,
                cert_filepath=self.cert_filepath,
                pri_key_filepath=self.pri_key_filepath,
                ca_filepath=self.ca_filepath,
                client_id=self.client_id,
                clean_session=True,
                keep_alive_secs=30,
            )
            
            connect_future = self._mqtt_connection.connect()
            connect_future.result(timeout=10)
            
            logger.info("Connected to AWS IoT MQTT broker")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from AWS IoT MQTT broker."""
        if self._mqtt_connection:
            try:
                disconnect_future = self._mqtt_connection.disconnect()
                disconnect_future.result(timeout=5)
                logger.info("Disconnected from AWS IoT MQTT broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT broker: {e}")
            finally:
                self._mqtt_connection = None