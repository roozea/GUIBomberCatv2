"""Tests para conexión MQTT.

Pruebas unitarias para la funcionalidad de conexión del servicio AWS IoT.
"""

import asyncio
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from modules.bombercat_mqtt import AWSIoTService, ConnectionStatus, MQTTConfig


class TestMQTTConfig:
    """Tests para configuración MQTT."""
    
    def test_config_creation(self):
        """Test creación de configuración básica."""
        config = MQTTConfig(
            endpoint="test.iot.region.amazonaws.com",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem"
        )
        
        assert config.endpoint == "test.iot.region.amazonaws.com"
        assert config.cert_path == "/path/to/cert.pem"
        assert config.key_path == "/path/to/key.pem"
        assert config.ca_path == "/path/to/ca.pem"
        assert config.client_id is not None
        assert config.device_id == config.client_id
    
    def test_config_with_custom_ids(self):
        """Test configuración con IDs personalizados."""
        config = MQTTConfig(
            endpoint="test.iot.region.amazonaws.com",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem",
            client_id="custom-client",
            device_id="custom-device"
        )
        
        assert config.client_id == "custom-client"
        assert config.device_id == "custom-device"
    
    def test_client_id_generation(self):
        """Test generación automática de client_id."""
        config1 = MQTTConfig(
            endpoint="test.iot.region.amazonaws.com",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem"
        )
        
        config2 = MQTTConfig(
            endpoint="test.iot.region.amazonaws.com",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem"
        )
        
        # Los client_id deben ser únicos
        assert config1.client_id != config2.client_id
        assert config1.client_id.startswith("bombercat-")
        assert len(config1.client_id) == len("bombercat-") + 8


class TestAWSIoTServiceCreation:
    """Tests para creación del servicio."""
    
    @patch('modules.bombercat_mqtt.aws_iot_service.mqtt_connection_builder')
    def test_service_creation(self, mock_builder):
        """Test creación básica del servicio."""
        # Mock de la conexión
        mock_connection = Mock()
        mock_builder.mtls_from_path.return_value = mock_connection
        
        config = MQTTConfig(
            endpoint="test.iot.region.amazonaws.com",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem"
        )
        
        service = AWSIoTService(config)
        
        assert service.config == config
        assert service.connection_status == ConnectionStatus.STOPPED
        assert not service.is_connected
        assert service._reconnect_attempts == 0
        
        # Verificar que se llamó al builder
        mock_builder.mtls_from_path.assert_called_once_with(
            endpoint=config.endpoint,
            cert_filepath=config.cert_path,
            pri_key_filepath=config.key_path,
            ca_filepath=config.ca_path,
            client_id=config.client_id,
            clean_session=False,
            keep_alive_secs=30,
            on_connection_interrupted=service._on_connection_interrupted_callback,
            on_connection_resumed=service._on_connection_resumed_callback
        )
    
    @patch.dict(os.environ, {
        'AWS_IOT_ENDPOINT': 'test.iot.region.amazonaws.com',
        'AWS_IOT_CERT_PATH': '/path/to/cert.pem',
        'AWS_IOT_KEY_PATH': '/path/to/key.pem',
        'AWS_IOT_CA_PATH': '/path/to/ca.pem',
        'AWS_IOT_CLIENT_ID': 'env-client'
    })
    @patch('modules.bombercat_mqtt.aws_iot_service.mqtt_connection_builder')
    def test_service_from_env(self, mock_builder):
        """Test creación desde variables de entorno."""
        mock_connection = Mock()
        mock_builder.mtls_from_path.return_value = mock_connection
        
        service = AWSIoTService.from_env(device_id="test-device")
        
        assert service.config.endpoint == "test.iot.region.amazonaws.com"
        assert service.config.cert_path == "/path/to/cert.pem"
        assert service.config.key_path == "/path/to/key.pem"
        assert service.config.ca_path == "/path/to/ca.pem"
        assert service.config.client_id == "env-client"
        assert service.config.device_id == "test-device"
    
    def test_service_from_env_missing_vars(self):
        """Test error cuando faltan variables de entorno."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Variables de entorno faltantes"):
                AWSIoTService.from_env()
    
    def test_service_without_awscrt(self):
        """Test error cuando awscrt no está disponible."""
        config = MQTTConfig(
            endpoint="test.iot.region.amazonaws.com",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
            ca_path="/path/to/ca.pem"
        )
        
        with patch('modules.bombercat_mqtt.aws_iot_service.mqtt', None):
            with pytest.raises(ImportError, match="awscrt y awsiot son requeridos"):
                AWSIoTService(config)


class TestAWSIoTServiceConnection:
    """Tests para funcionalidad de conexión."""
    
    @pytest.fixture
    def mock_service(self):
        """Fixture para servicio mockeado."""
        with patch('modules.bombercat_mqtt.aws_iot_service.mqtt_connection_builder') as mock_builder:
            mock_connection = Mock()
            mock_builder.mtls_from_path.return_value = mock_connection
            
            config = MQTTConfig(
                endpoint="test.iot.region.amazonaws.com",
                cert_path="/path/to/cert.pem",
                key_path="/path/to/key.pem",
                ca_path="/path/to/ca.pem"
            )
            
            service = AWSIoTService(config)
            service._connection = mock_connection
            
            return service, mock_connection
    
    @pytest.mark.asyncio
    async def test_successful_start(self, mock_service):
        """Test inicio exitoso del servicio."""
        service, mock_connection = mock_service
        
        # Mock del connect future
        connect_future = asyncio.Future()
        connect_future.set_result(None)
        mock_connection.connect.return_value = connect_future
        
        # Mock del publish para el evento de conexión
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Iniciar servicio
        result = await service.start()
        
        assert result is True
        assert service.connection_status == ConnectionStatus.CONNECTED
        assert service.is_connected
        assert service._reconnect_attempts == 0
        
        # Verificar que se llamó connect
        mock_connection.connect.assert_called_once()
        
        # Verificar que se publicó evento de conexión
        mock_connection.publish.assert_called()
        
        # Limpiar
        await service.stop()
    
    @pytest.mark.asyncio
    async def test_start_failure(self, mock_service):
        """Test fallo en el inicio del servicio."""
        service, mock_connection = mock_service
        
        # Mock del connect future con error
        connect_future = asyncio.Future()
        connect_future.set_exception(Exception("Connection failed"))
        mock_connection.connect.return_value = connect_future
        
        # Iniciar servicio
        result = await service.start()
        
        assert result is False
        assert service.connection_status == ConnectionStatus.STOPPED
        assert not service.is_connected
    
    @pytest.mark.asyncio
    async def test_start_already_started(self, mock_service):
        """Test inicio cuando ya está iniciado."""
        service, mock_connection = mock_service
        
        # Simular que ya está conectado
        service._status = ConnectionStatus.CONNECTED
        
        result = await service.start()
        
        assert result is True
        # No debe llamar connect
        mock_connection.connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_stop_service(self, mock_service):
        """Test detener servicio."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del disconnect future
        disconnect_future = asyncio.Future()
        disconnect_future.set_result(None)
        mock_connection.disconnect.return_value = disconnect_future
        
        # Mock del publish para el evento de desconexión
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Detener servicio
        await service.stop()
        
        assert service.connection_status == ConnectionStatus.STOPPED
        assert not service.is_connected
        
        # Verificar que se llamó disconnect
        mock_connection.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_already_stopped(self, mock_service):
        """Test detener cuando ya está detenido."""
        service, mock_connection = mock_service
        
        # Ya está detenido por defecto
        assert service.connection_status == ConnectionStatus.STOPPED
        
        await service.stop()
        
        # No debe llamar disconnect
        mock_connection.disconnect.assert_not_called()
    
    def test_status_method(self, mock_service):
        """Test método status."""
        service, _ = mock_service
        
        status = service.status()
        
        assert isinstance(status, dict)
        assert "connection_status" in status
        assert "connected" in status
        assert "reconnect_attempts" in status
        assert "last_publish_ts" in status
        assert "client_id" in status
        assert "device_id" in status
        assert "endpoint" in status
        
        assert status["connection_status"] == ConnectionStatus.STOPPED.value
        assert status["connected"] is False
        assert status["reconnect_attempts"] == 0
        assert status["client_id"] == service.config.client_id
    
    def test_repr(self, mock_service):
        """Test representación string."""
        service, _ = mock_service
        
        repr_str = repr(service)
        
        assert "AWSIoTService" in repr_str
        assert service.config.client_id in repr_str
        assert "stopped" in repr_str


class TestConnectionCallbacks:
    """Tests para callbacks de conexión."""
    
    @pytest.fixture
    def mock_service(self):
        """Fixture para servicio mockeado."""
        with patch('modules.bombercat_mqtt.aws_iot_service.mqtt_connection_builder') as mock_builder:
            mock_connection = Mock()
            mock_builder.mtls_from_path.return_value = mock_connection
            
            config = MQTTConfig(
                endpoint="test.iot.region.amazonaws.com",
                cert_path="/path/to/cert.pem",
                key_path="/path/to/key.pem",
                ca_path="/path/to/ca.pem"
            )
            
            service = AWSIoTService(config)
            service._connection = mock_connection
            
            return service, mock_connection
    
    @pytest.mark.asyncio
    async def test_connection_interrupted_callback(self, mock_service):
        """Test callback de conexión interrumpida."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock asyncio.get_running_loop para simular un loop corriendo
        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop
            
            # Llamar callback
            service._on_connection_interrupted_callback(
                mock_connection, 
                Exception("Network error"),
                **{}
            )
            
            assert service.connection_status == ConnectionStatus.DISCONNECTED
            # Verificar que se intentó crear la tarea de reconexión
            mock_loop.create_task.assert_called_once()
    
    def test_connection_resumed_callback(self, mock_service):
        """Test callback de conexión restablecida."""
        service, mock_connection = mock_service
        
        # Simular que está reconectando
        service._status = ConnectionStatus.RECONNECTING
        service._reconnect_attempts = 3
        
        # Mock asyncio.create_task para evitar crear tareas reales
        with patch('asyncio.create_task') as mock_create_task:
            # Llamar callback
            service._on_connection_resumed_callback(
                mock_connection,
                return_code=0,
                session_present=False,
                **{}
            )
            
            assert service.connection_status == ConnectionStatus.CONNECTED
            assert service._reconnect_attempts == 0