"""Tests para publicación de mensajes.

Pruebas unitarias para la funcionalidad de publicación del servicio AWS IoT.
"""

import asyncio
import json
import time
import pytest
from unittest.mock import Mock, AsyncMock, patch, call

from modules.bombercat_mqtt import AWSIoTService, ConnectionStatus, MQTTConfig


class TestMessagePublishing:
    """Tests para publicación de mensajes."""
    
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
                ca_path="/path/to/ca.pem",
                client_id="test-client",
                device_id="test-device"
            )
            
            service = AWSIoTService(config)
            service._connection = mock_connection
            
            return service, mock_connection
    
    @pytest.mark.asyncio
    async def test_publish_telemetry_success(self, mock_service):
        """Test publicación exitosa de telemetría."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del publish future
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Datos de telemetría
        telemetry_data = {
            "temperature": 25.5,
            "humidity": 60.0,
            "pressure": 1013.25
        }
        
        # Publicar telemetría
        with patch('time.time', return_value=1234567890.0):
            result = await service.publish_telemetry(telemetry_data)
        
        assert result is True
        assert service._last_publish_ts == 1234567890.0
        
        # Verificar llamada a publish
        mock_connection.publish.assert_called_once()
        call_args = mock_connection.publish.call_args
        
        assert call_args[1]['topic'] == service.TELEMETRY_TOPIC
        assert call_args[1]['qos'] == service.QOS
        
        # Verificar payload
        payload_str = call_args[1]['payload']
        payload = json.loads(payload_str)
        
        assert payload['timestamp'] == 1234567890.0
        assert payload['device_id'] == "test-device"
        assert payload['data'] == telemetry_data
    
    @pytest.mark.asyncio
    async def test_publish_event_success(self, mock_service):
        """Test publicación exitosa de evento."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del publish future
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Datos de evento
        event_type = "sensor_alert"
        event_metadata = {
            "sensor_id": "temp_01",
            "threshold": 30.0,
            "current_value": 35.2,
            "severity": "warning"
        }
        
        # Publicar evento
        with patch('time.time', return_value=1234567890.0):
            result = await service.publish_event(event_type, event_metadata)
        
        assert result is True
        assert service._last_publish_ts == 1234567890.0
        
        # Verificar llamada a publish
        mock_connection.publish.assert_called_once()
        call_args = mock_connection.publish.call_args
        
        assert call_args[1]['topic'] == service.EVENTS_TOPIC
        assert call_args[1]['qos'] == service.QOS
        
        # Verificar payload
        payload_str = call_args[1]['payload']
        payload = json.loads(payload_str)
        
        assert payload['timestamp'] == 1234567890.0
        assert payload['device_id'] == "test-device"
        assert payload['event'] == event_type
        assert payload['metadata'] == event_metadata
    
    @pytest.mark.asyncio
    async def test_publish_when_disconnected(self, mock_service):
        """Test publicación cuando está desconectado."""
        service, mock_connection = mock_service
        
        # Simular que está desconectado
        service._status = ConnectionStatus.DISCONNECTED
        
        # Intentar publicar telemetría
        result = await service.publish_telemetry({"test": "data"})
        
        assert result is False
        
        # No debe llamar publish
        mock_connection.publish.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_publish_failure(self, mock_service):
        """Test fallo en publicación."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del publish future con error
        publish_future = asyncio.Future()
        publish_future.set_exception(Exception("Publish failed"))
        mock_connection.publish.return_value = publish_future
        
        # Intentar publicar telemetría
        result = await service.publish_telemetry({"test": "data"})
        
        assert result is False
        assert service._last_publish_ts is None
    
    @pytest.mark.asyncio
    async def test_publish_with_unicode_data(self, mock_service):
        """Test publicación con datos Unicode."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del publish future
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Datos con caracteres Unicode
        telemetry_data = {
            "location": "São Paulo",
            "description": "Medición de temperatura en °C",
            "status": "Funcionando correctamente ✓"
        }
        
        # Publicar telemetría
        result = await service.publish_telemetry(telemetry_data)
        
        assert result is True
        
        # Verificar que el JSON se serializa correctamente
        call_args = mock_connection.publish.call_args
        payload_str = call_args[1]['payload']
        payload = json.loads(payload_str)
        
        assert payload['data'] == telemetry_data
    
    @pytest.mark.asyncio
    async def test_publish_large_payload(self, mock_service):
        """Test publicación con payload grande."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del publish future
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Crear payload grande
        large_data = {
            "readings": [{
                "sensor_id": f"sensor_{i:04d}",
                "value": i * 0.1,
                "timestamp": 1234567890 + i
            } for i in range(1000)]
        }
        
        # Publicar telemetría
        result = await service.publish_telemetry(large_data)
        
        assert result is True
        
        # Verificar que se llamó publish
        mock_connection.publish.assert_called_once()
        
        # Verificar tamaño del payload
        call_args = mock_connection.publish.call_args
        payload_str = call_args[1]['payload']
        
        # El payload debe ser considerable
        assert len(payload_str) > 10000
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_publishes(self, mock_service):
        """Test múltiples publicaciones concurrentes."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Contador para verificar llamadas
        call_count = 0
        
        # Mock del publish future
        def create_publish_future(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            future = asyncio.Future()
            future.set_result(None)
            return future
        
        mock_connection.publish.side_effect = create_publish_future
        
        # Crear múltiples tareas de publicación
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                # Telemetría
                task = service.publish_telemetry({"reading": i})
            else:
                # Evento
                task = service.publish_event("test_event", {"index": i})
            tasks.append(task)
        
        # Ejecutar todas las tareas concurrentemente
        results = await asyncio.gather(*tasks)
        
        # Todas deben ser exitosas
        assert all(results), f"Some publishes failed: {results}"
        
        # Debe haber 10 llamadas a publish
        assert call_count == 10, f"Expected 10 calls, got {call_count}"
        assert mock_connection.publish.call_count == 10
    
    @pytest.mark.asyncio
    async def test_publish_updates_last_publish_timestamp(self, mock_service):
        """Test que la publicación actualiza el timestamp."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        
        # Mock del publish future
        publish_future = asyncio.Future()
        publish_future.set_result(None)
        mock_connection.publish.return_value = publish_future
        
        # Timestamp inicial debe ser None
        assert service._last_publish_ts is None
        
        # Publicar mensaje
        current_time = time.time()
        with patch('time.time', return_value=current_time):
            await service.publish_telemetry({"test": "data"})
        
        # Timestamp debe actualizarse
        assert service._last_publish_ts == current_time
        
        # Verificar en status
        status = service.status()
        assert status['last_publish_ts'] == current_time


class TestTopicsAndQoS:
    """Tests para tópicos y QoS."""
    
    def test_topic_constants(self):
        """Test constantes de tópicos."""
        assert AWSIoTService.TELEMETRY_TOPIC == "bombercat/telemetry"
        assert AWSIoTService.EVENTS_TOPIC == "bombercat/events"
    
    def test_qos_setting(self):
        """Test configuración de QoS."""
        # QoS debe ser AT_LEAST_ONCE (1)
        with patch('modules.bombercat_mqtt.aws_iot_service.mqtt') as mock_mqtt:
            mock_mqtt.QoS.AT_LEAST_ONCE = 1
            assert AWSIoTService.QOS == 1
    
    @pytest.mark.asyncio
    async def test_publish_uses_correct_qos(self):
        """Test que la publicación usa el QoS correcto."""
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
            service._status = ConnectionStatus.CONNECTED
            
            # Mock del publish future
            publish_future = asyncio.Future()
            publish_future.set_result(None)
            mock_connection.publish.return_value = publish_future
            
            # Publicar mensaje
            await service.publish_telemetry({"test": "data"})
            
            # Verificar QoS
            call_args = mock_connection.publish.call_args
            assert call_args[1]['qos'] == service.QOS


class TestPayloadFormat:
    """Tests para formato de payload."""
    
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
                ca_path="/path/to/ca.pem",
                client_id="test-client",
                device_id="test-device"
            )
            
            service = AWSIoTService(config)
            service._connection = mock_connection
            service._status = ConnectionStatus.CONNECTED
            
            # Mock del publish future
            publish_future = asyncio.Future()
            publish_future.set_result(None)
            mock_connection.publish.return_value = publish_future
            
            return service, mock_connection
    
    @pytest.mark.asyncio
    async def test_telemetry_payload_format(self, mock_service):
        """Test formato de payload de telemetría."""
        service, mock_connection = mock_service
        
        test_data = {"temperature": 25.0, "humidity": 60}
        
        with patch('time.time', return_value=1234567890.123):
            await service.publish_telemetry(test_data)
        
        # Obtener payload
        call_args = mock_connection.publish.call_args
        payload_str = call_args[1]['payload']
        payload = json.loads(payload_str)
        
        # Verificar estructura
        assert 'timestamp' in payload
        assert 'device_id' in payload
        assert 'data' in payload
        
        # Verificar valores
        assert payload['timestamp'] == 1234567890.123
        assert payload['device_id'] == "test-device"
        assert payload['data'] == test_data
    
    @pytest.mark.asyncio
    async def test_event_payload_format(self, mock_service):
        """Test formato de payload de evento."""
        service, mock_connection = mock_service
        
        event_type = "alert"
        metadata = {"level": "warning", "source": "sensor_01"}
        
        with patch('time.time', return_value=1234567890.456):
            await service.publish_event(event_type, metadata)
        
        # Obtener payload
        call_args = mock_connection.publish.call_args
        payload_str = call_args[1]['payload']
        payload = json.loads(payload_str)
        
        # Verificar estructura
        assert 'timestamp' in payload
        assert 'device_id' in payload
        assert 'event' in payload
        assert 'metadata' in payload
        
        # Verificar valores
        assert payload['timestamp'] == 1234567890.456
        assert payload['device_id'] == "test-device"
        assert payload['event'] == event_type
        assert payload['metadata'] == metadata
    
    @pytest.mark.asyncio
    async def test_json_serialization(self, mock_service):
        """Test serialización JSON."""
        service, mock_connection = mock_service
        
        # Datos complejos
        complex_data = {
            "string": "test",
            "number": 42,
            "float": 3.14159,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }
        
        await service.publish_telemetry(complex_data)
        
        # Obtener payload y verificar que es JSON válido
        call_args = mock_connection.publish.call_args
        payload_str = call_args[1]['payload']
        
        # Debe poder parsearse como JSON
        payload = json.loads(payload_str)
        assert payload['data'] == complex_data
        
        # Verificar que ensure_ascii=False funciona
        unicode_data = {"message": "Hola, ¿cómo estás? 🌟"}
        await service.publish_telemetry(unicode_data)
        
        # El payload debe contener caracteres Unicode sin escapar
        call_args = mock_connection.publish.call_args
        payload_str = call_args[1]['payload']
        assert "🌟" in payload_str
        assert "¿" in payload_str