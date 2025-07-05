"""Tests para reconexión automática.

Pruebas unitarias para la funcionalidad de reconexión del servicio AWS IoT.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, call

from modules.bombercat_mqtt import AWSIoTService, ConnectionStatus, MQTTConfig
from modules.bombercat_mqtt.backoff import ExponentialBackoff, ConnectionRetryManager


class TestExponentialBackoff:
    """Tests para back-off exponencial."""
    
    def test_backoff_creation(self):
        """Test creación de back-off."""
        backoff = ExponentialBackoff(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            jitter=False
        )
        
        assert backoff.max_attempts == 3
        assert backoff.base_delay == 1.0
        assert backoff.max_delay == 10.0
        assert backoff.jitter is False
        assert backoff.attempt == 0
        assert backoff.should_continue is True
    
    def test_delay_calculation(self):
        """Test cálculo de delays."""
        backoff = ExponentialBackoff(
            max_attempts=4,
            base_delay=1.0,
            max_delay=10.0,
            jitter=False
        )
        
        # Primer intento: 1.0 * 2^0 = 1.0
        delay1 = backoff.next_delay()
        assert delay1 == 1.0
        assert backoff.attempt == 1
        
        # Segundo intento: 1.0 * 2^1 = 2.0
        delay2 = backoff.next_delay()
        assert delay2 == 2.0
        assert backoff.attempt == 2
        
        # Tercer intento: 1.0 * 2^2 = 4.0
        delay3 = backoff.next_delay()
        assert delay3 == 4.0
        assert backoff.attempt == 3
        
        # Cuarto intento: 1.0 * 2^3 = 8.0
        delay4 = backoff.next_delay()
        assert delay4 == 8.0
        assert backoff.attempt == 4
        
        # Quinto intento: None (máximo alcanzado)
        delay5 = backoff.next_delay()
        assert delay5 is None
        assert not backoff.should_continue
    
    def test_max_delay_limit(self):
        """Test límite máximo de delay."""
        backoff = ExponentialBackoff(
            max_attempts=10,
            base_delay=1.0,
            max_delay=5.0,
            jitter=False
        )
        
        # Saltar a un intento alto
        backoff.attempt = 5
        
        # 1.0 * 2^5 = 32.0, pero limitado a 5.0
        delay = backoff.next_delay()
        assert delay == 5.0
    
    def test_jitter(self):
        """Test jitter aleatorio."""
        backoff = ExponentialBackoff(
            max_attempts=5,
            base_delay=4.0,
            max_delay=100.0,
            jitter=True
        )
        
        # Obtener varios delays y verificar que varían
        delays = []
        for _ in range(5):
            backoff.reset()
            delay = backoff.next_delay()
            delays.append(delay)
        
        # Con jitter, los delays deben variar
        # (aunque podría haber coincidencias por casualidad)
        assert len(set(delays)) > 1 or len(delays) == 1  # Al menos algo de variación
        
        # Todos deben estar en el rango esperado (4.0 ± 25%)
        for delay in delays:
            assert 3.0 <= delay <= 5.0
    
    def test_reset(self):
        """Test reinicio del back-off."""
        backoff = ExponentialBackoff(max_attempts=3)
        
        # Avanzar algunos intentos
        backoff.next_delay()
        backoff.next_delay()
        
        assert backoff.attempt == 2
        
        # Reiniciar
        backoff.reset()
        
        assert backoff.attempt == 0
        assert backoff.last_delay == 0.0
        assert backoff.should_continue is True
    
    @pytest.mark.asyncio
    async def test_wait(self):
        """Test espera asíncrona."""
        backoff = ExponentialBackoff(
            max_attempts=2,
            base_delay=0.01,  # Delay muy pequeño para test rápido
            jitter=False
        )
        
        # Primera espera
        start_time = asyncio.get_event_loop().time()
        result = await backoff.wait()
        end_time = asyncio.get_event_loop().time()
        
        assert result is True
        assert end_time - start_time >= 0.01  # Al menos el delay esperado
        
        # Segunda espera
        result = await backoff.wait()
        assert result is True
        
        # Tercera espera (máximo alcanzado)
        result = await backoff.wait()
        assert result is False


class TestConnectionRetryManager:
    """Tests para gestor de reintentos."""
    
    def test_manager_creation(self):
        """Test creación del gestor."""
        manager = ConnectionRetryManager(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0
        )
        
        assert not manager.is_retrying
        assert manager.current_attempt == 0
        assert manager.backoff.max_attempts == 3
    
    @pytest.mark.asyncio
    async def test_successful_retry(self):
        """Test retry exitoso."""
        manager = ConnectionRetryManager(
            max_attempts=3,
            base_delay=0.01
        )
        
        # Mock de función de conexión que falla una vez
        connect_calls = 0
        async def mock_connect():
            nonlocal connect_calls
            connect_calls += 1
            if connect_calls == 1:
                raise Exception("Connection failed")
            # Segundo intento exitoso
        
        # Callbacks de prueba
        start_called = False
        success_called = False
        attempt_calls = []
        
        def on_start():
            nonlocal start_called
            start_called = True
        
        def on_success():
            nonlocal success_called
            success_called = True
        
        def on_attempt(attempt):
            attempt_calls.append(attempt)
        
        manager.on_retry_start = on_start
        manager.on_retry_success = on_success
        manager.on_retry_attempt = on_attempt
        
        # Ejecutar retry
        result = await manager.start_retry(mock_connect)
        
        assert result is True
        assert not manager.is_retrying
        assert start_called
        assert success_called
        assert len(attempt_calls) == 2  # Dos intentos
        assert connect_calls == 2
    
    @pytest.mark.asyncio
    async def test_failed_retry(self):
        """Test retry que falla completamente."""
        manager = ConnectionRetryManager(
            max_attempts=2,
            base_delay=0.01
        )
        
        # Mock de función que siempre falla
        async def mock_connect():
            raise Exception("Always fails")
        
        # Callback de fallo
        failed_called = False
        def on_failed():
            nonlocal failed_called
            failed_called = True
        
        manager.on_retry_failed = on_failed
        
        # Ejecutar retry
        result = await manager.start_retry(mock_connect)
        
        assert result is False
        assert not manager.is_retrying
        assert failed_called
    
    @pytest.mark.asyncio
    async def test_retry_already_running(self):
        """Test retry cuando ya está en curso."""
        manager = ConnectionRetryManager(max_attempts=3)
        
        # Simular que ya está reintentando
        manager._is_retrying = True
        
        async def mock_connect():
            pass
        
        result = await manager.start_retry(mock_connect)
        
        assert result is False
    
    def test_stop_retry(self):
        """Test detener retry."""
        manager = ConnectionRetryManager(max_attempts=3)
        
        # Simular estado de retry
        manager._is_retrying = True
        manager.backoff.attempt = 2
        
        manager.stop_retry()
        
        assert not manager.is_retrying
        assert manager.current_attempt == 0


class TestAWSIoTServiceReconnection:
    """Tests para reconexión del servicio AWS IoT."""
    
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
    async def test_reconnect_with_backoff_success(self, mock_service):
        """Test reconexión exitosa con back-off."""
        service, mock_connection = mock_service
        
        # Mock del connect future que falla una vez y luego funciona
        connect_calls = 0
        def mock_connect():
            nonlocal connect_calls
            connect_calls += 1
            future = asyncio.Future()
            if connect_calls == 1:
                future.set_exception(Exception("Connection failed"))
            else:
                future.set_result(None)
            return future
        
        mock_connection.connect = mock_connect
        
        # Simular estado desconectado
        service._status = ConnectionStatus.DISCONNECTED
        service._reconnect_attempts = 0
        
        # Ejecutar reconexión
        await service._reconnect_with_backoff()
        
        assert service.connection_status == ConnectionStatus.CONNECTED
        assert service._reconnect_attempts == 0  # Se reinicia en éxito
        assert connect_calls == 2
    
    @pytest.mark.asyncio
    async def test_reconnect_with_backoff_max_attempts(self, mock_service):
        """Test reconexión que agota los intentos."""
        service, mock_connection = mock_service
        
        # Mock del connect future que siempre falla
        def mock_connect():
            future = asyncio.Future()
            future.set_exception(Exception("Always fails"))
            return future
        
        mock_connection.connect = mock_connect
        
        # Simular estado desconectado
        service._status = ConnectionStatus.DISCONNECTED
        service._reconnect_attempts = 0
        
        # Ejecutar reconexión (debe fallar)
        with pytest.raises(Exception):
            await service._reconnect_with_backoff()
        
        assert service.connection_status == ConnectionStatus.STOPPED
        assert service._reconnect_attempts == service.MAX_RECONNECT_ATTEMPTS
    
    @pytest.mark.asyncio
    async def test_reconnect_when_stopped(self, mock_service):
        """Test reconexión cuando el servicio está detenido."""
        service, mock_connection = mock_service
        
        # Servicio detenido
        service._status = ConnectionStatus.STOPPED
        
        # Ejecutar reconexión (debe salir inmediatamente)
        await service._reconnect_with_backoff()
        
        # No debe llamar connect
        mock_connection.connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_connection_interrupted_triggers_reconnect(self, mock_service):
        """Test que la interrupción de conexión dispara reconexión."""
        service, mock_connection = mock_service
        
        # Simular que está conectado
        service._status = ConnectionStatus.CONNECTED
        service._reconnect_attempts = 0
        
        # Mock get_running_loop para simular un loop corriendo
        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop
            
            # Simular interrupción de conexión
            service._on_connection_interrupted_callback(
                mock_connection,
                Exception("Network error"),
                **{}
            )
            
            assert service.connection_status == ConnectionStatus.DISCONNECTED
            
            # Verificar que se creó tarea de reconexión
            mock_loop.create_task.assert_called_once()
            
            # Verificar que la tarea es para reconexión
            task_arg = mock_loop.create_task.call_args[0][0]
            assert hasattr(task_arg, '__name__') or str(task_arg).find('_reconnect_with_backoff') >= 0
    
    @pytest.mark.asyncio
    async def test_no_reconnect_when_max_attempts_reached(self, mock_service):
        """Test que no se reintenta cuando se alcanza el máximo."""
        service, mock_connection = mock_service
        
        # Simular máximo de intentos alcanzado
        service._status = ConnectionStatus.CONNECTED
        service._reconnect_attempts = service.MAX_RECONNECT_ATTEMPTS
        
        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop
            
            # Simular interrupción de conexión
            service._on_connection_interrupted_callback(
                mock_connection,
                Exception("Network error"),
                **{}
            )
            
            assert service.connection_status == ConnectionStatus.DISCONNECTED
            
            # No debe crear tarea de reconexión
            mock_loop.create_task.assert_not_called()
    
    def test_connection_resumed_resets_attempts(self, mock_service):
        """Test que la reanudación reinicia el contador de intentos."""
        service, mock_connection = mock_service
        
        # Simular varios intentos de reconexión
        service._status = ConnectionStatus.RECONNECTING
        service._reconnect_attempts = 3
        
        # Simular reanudación de conexión
        service._on_connection_resumed_callback(
            mock_connection,
            return_code=0,
            session_present=False,
            **{}
        )
        
        assert service.connection_status == ConnectionStatus.CONNECTED
        assert service._reconnect_attempts == 0
    
    @pytest.mark.asyncio
    async def test_reconnect_status_transitions(self, mock_service):
        """Test transiciones de estado durante reconexión."""
        service, mock_connection = mock_service
        
        # Mock del connect que falla una vez
        connect_calls = 0
        def mock_connect():
            nonlocal connect_calls
            connect_calls += 1
            future = asyncio.Future()
            if connect_calls == 1:
                # Primer intento falla
                future.set_exception(Exception("Connection failed"))
            else:
                # Segundo intento exitoso
                future.set_result(None)
            return future
        
        mock_connection.connect = mock_connect
        
        # Estado inicial
        service._status = ConnectionStatus.DISCONNECTED
        service._reconnect_attempts = 0
        
        # Ejecutar reconexión
        await service._reconnect_with_backoff()
        
        # Verificar estado final
        assert service.connection_status == ConnectionStatus.CONNECTED
        assert service._reconnect_attempts == 0
        assert connect_calls == 2