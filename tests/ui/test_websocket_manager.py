"""Tests para WebSocket Manager.

Testa la funcionalidad de conexión, reconexión y manejo de mensajes
del WebSocket Manager con mocks apropiados.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from websockets.exceptions import ConnectionClosed, InvalidURI

from ui.websocket_manager import WSManager, ConnectionState, WSMessage


class TestWSManager:
    """Tests para la clase WSManager."""
    
    @pytest.fixture
    def ws_manager(self):
        """Fixture que crea un WSManager para testing."""
        return WSManager("ws://localhost:8000/ws", max_retries=3)
        
    @pytest.fixture
    def mock_websocket(self):
        """Fixture que crea un mock de websocket."""
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = AsyncMock(return_value=iter([]))
        return mock_ws
        
    def test_initialization(self, ws_manager):
        """Testa la inicialización del WSManager."""
        assert ws_manager.url == "ws://localhost:8000/ws"
        assert ws_manager.max_retries == 3
        assert ws_manager.state == ConnectionState.DISCONNECTED
        assert not ws_manager.connected
        assert ws_manager.subscribers == []
        assert ws_manager.retry_count == 0
        
    @pytest.mark.asyncio
    async def test_successful_connection(self, ws_manager, mock_websocket):
        """Testa conexión exitosa."""
        with patch('websockets.connect', return_value=mock_websocket):
            result = await ws_manager.connect()
            
        assert result is True
        assert ws_manager.connected
        assert ws_manager.state == ConnectionState.CONNECTED
        assert ws_manager.retry_count == 0
        assert ws_manager.websocket == mock_websocket
        
    @pytest.mark.asyncio
    async def test_connection_failure(self, ws_manager):
        """Testa fallo en la conexión."""
        with patch('websockets.connect', side_effect=ConnectionClosed(None, None)):
            result = await ws_manager.connect()
            
        assert result is False
        assert not ws_manager.connected
        assert ws_manager.state == ConnectionState.DISCONNECTED
        assert ws_manager.websocket is None
        
    @pytest.mark.asyncio
    async def test_connection_invalid_uri(self, ws_manager):
        """Testa conexión con URI inválida."""
        with patch('websockets.connect', side_effect=InvalidURI("invalid")):
            result = await ws_manager.connect()
            
        assert result is False
        assert not ws_manager.connected
        assert ws_manager.state == ConnectionState.DISCONNECTED
        
    @pytest.mark.asyncio
    async def test_disconnect(self, ws_manager, mock_websocket):
        """Testa desconexión."""
        # Simular conexión establecida
        ws_manager.websocket = mock_websocket
        ws_manager.state = ConnectionState.CONNECTED
        ws_manager.listen_task = AsyncMock()
        ws_manager.reconnect_task = AsyncMock()
        
        await ws_manager.disconnect()
        
        assert ws_manager.state == ConnectionState.DISCONNECTED
        assert ws_manager.websocket is None
        mock_websocket.close.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_send_message_success(self, ws_manager, mock_websocket):
        """Testa envío exitoso de mensaje."""
        # Configurar conexión
        ws_manager.websocket = mock_websocket
        ws_manager.state = ConnectionState.CONNECTED
        
        message = {"cmd": "test", "data": {"value": 123}}
        result = await ws_manager.send(message)
        
        assert result is True
        mock_websocket.send.assert_called_once_with(json.dumps(message))
        
    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, ws_manager):
        """Testa envío de mensaje sin conexión."""
        message = {"cmd": "test"}
        result = await ws_manager.send(message)
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_send_message_connection_error(self, ws_manager, mock_websocket):
        """Testa envío de mensaje con error de conexión."""
        # Configurar conexión
        ws_manager.websocket = mock_websocket
        ws_manager.state = ConnectionState.CONNECTED
        mock_websocket.send.side_effect = ConnectionClosed(None, None)
        
        with patch.object(ws_manager, '_handle_disconnect') as mock_handle:
            message = {"cmd": "test"}
            result = await ws_manager.send(message)
            
        assert result is False
        mock_handle.assert_called_once()
        
    def test_subscribe_unsubscribe(self, ws_manager):
        """Testa suscripción y desuscripción de callbacks."""
        callback1 = MagicMock()
        callback2 = MagicMock()
        
        # Suscribir callbacks
        ws_manager.subscribe(callback1)
        ws_manager.subscribe(callback2)
        
        assert len(ws_manager.subscribers) == 2
        assert callback1 in ws_manager.subscribers
        assert callback2 in ws_manager.subscribers
        
        # No duplicar suscripciones
        ws_manager.subscribe(callback1)
        assert len(ws_manager.subscribers) == 2
        
        # Desuscribir
        ws_manager.unsubscribe(callback1)
        assert len(ws_manager.subscribers) == 1
        assert callback1 not in ws_manager.subscribers
        assert callback2 in ws_manager.subscribers
        
    @pytest.mark.asyncio
    async def test_reconnect_success(self, ws_manager, mock_websocket):
        """Testa reconexión exitosa."""
        ws_manager.retry_count = 1
        
        with patch('websockets.connect', return_value=mock_websocket):
            with patch('asyncio.sleep') as mock_sleep:
                result = await ws_manager.reconnect()
                
        assert result is True
        assert ws_manager.connected
        assert ws_manager.retry_count == 1  # Se incrementa en reconnect
        mock_sleep.assert_called_once_with(1)  # 2^(1-1) = 1 segundo
        
    @pytest.mark.asyncio
    async def test_reconnect_max_retries(self, ws_manager):
        """Testa reconexión con máximo de reintentos alcanzado."""
        ws_manager.retry_count = 3  # Igual al max_retries
        
        result = await ws_manager.reconnect()
        
        assert result is False
        assert ws_manager.state == ConnectionState.FAILED
        
    @pytest.mark.asyncio
    async def test_reconnect_exponential_backoff(self, ws_manager, mock_websocket):
        """Testa backoff exponencial en reconexión."""
        test_cases = [
            (1, 1),   # 2^0 = 1
            (2, 2),   # 2^1 = 2
            (3, 4),   # 2^2 = 4
            (4, 8),   # 2^3 = 8
            (5, 16),  # 2^4 = 16
            (6, 16),  # max 16
        ]
        
        for retry_count, expected_delay in test_cases:
            ws_manager.retry_count = retry_count - 1
            
            with patch('websockets.connect', return_value=mock_websocket):
                with patch('asyncio.sleep') as mock_sleep:
                    await ws_manager.reconnect()
                    
            mock_sleep.assert_called_with(expected_delay)
            
    @pytest.mark.asyncio
    async def test_listen_message_processing(self, ws_manager):
        """Testa procesamiento de mensajes en _listen."""
        # Crear mock de websocket que retorna mensajes
        messages = [
            json.dumps({"type": "test", "data": {"value": 1}, "timestamp": 123.45}),
            json.dumps({"type": "info", "data": {"msg": "hello"}}),
        ]
        
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__ = AsyncMock(return_value=iter(messages))
        ws_manager.websocket = mock_websocket
        
        # Crear callback mock
        callback = MagicMock()
        ws_manager.subscribe(callback)
        
        # Ejecutar _listen
        await ws_manager._listen()
        
        # Verificar que se llamó el callback para cada mensaje
        assert callback.call_count == 2
        
        # Verificar primer mensaje
        first_call_args = callback.call_args_list[0][0][0]
        assert isinstance(first_call_args, WSMessage)
        assert first_call_args.type == "test"
        assert first_call_args.data == {"value": 1}
        assert first_call_args.timestamp == 123.45
        
        # Verificar segundo mensaje (sin timestamp)
        second_call_args = callback.call_args_list[1][0][0]
        assert isinstance(second_call_args, WSMessage)
        assert second_call_args.type == "info"
        assert second_call_args.data == {"msg": "hello"}
        
    @pytest.mark.asyncio
    async def test_listen_invalid_json(self, ws_manager):
        """Testa manejo de JSON inválido en _listen."""
        # Mensaje con JSON inválido
        invalid_message = "invalid json{"
        
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__ = AsyncMock(return_value=iter([invalid_message]))
        ws_manager.websocket = mock_websocket
        
        callback = MagicMock()
        ws_manager.subscribe(callback)
        
        # Ejecutar _listen (no debería lanzar excepción)
        await ws_manager._listen()
        
        # El callback no debería haberse llamado
        callback.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_listen_callback_exception(self, ws_manager):
        """Testa manejo de excepciones en callbacks."""
        message = json.dumps({"type": "test", "data": {}})
        
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__ = AsyncMock(return_value=iter([message]))
        ws_manager.websocket = mock_websocket
        
        # Callback que lanza excepción
        failing_callback = MagicMock(side_effect=Exception("Test error"))
        working_callback = MagicMock()
        
        ws_manager.subscribe(failing_callback)
        ws_manager.subscribe(working_callback)
        
        # Ejecutar _listen (no debería lanzar excepción)
        await ws_manager._listen()
        
        # Ambos callbacks deberían haberse llamado
        failing_callback.assert_called_once()
        working_callback.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_listen_connection_closed(self, ws_manager):
        """Testa manejo de conexión cerrada en _listen."""
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__ = AsyncMock(side_effect=ConnectionClosed(None, None))
        ws_manager.websocket = mock_websocket
        
        with patch.object(ws_manager, '_handle_disconnect') as mock_handle:
            await ws_manager._listen()
            
        mock_handle.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_handle_disconnect(self, ws_manager):
        """Testa manejo de desconexión inesperada."""
        ws_manager.state = ConnectionState.CONNECTED
        
        with patch.object(ws_manager, '_auto_reconnect') as mock_auto_reconnect:
            with patch('asyncio.create_task') as mock_create_task:
                await ws_manager._handle_disconnect()
                
        assert ws_manager.state == ConnectionState.DISCONNECTED
        mock_create_task.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_auto_reconnect_success(self, ws_manager, mock_websocket):
        """Testa reconexión automática exitosa."""
        ws_manager.retry_count = 0
        ws_manager.state = ConnectionState.DISCONNECTED
        
        with patch.object(ws_manager, 'reconnect', return_value=True) as mock_reconnect:
            await ws_manager._auto_reconnect()
            
        mock_reconnect.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_auto_reconnect_failure(self, ws_manager):
        """Testa reconexión automática fallida."""
        ws_manager.retry_count = 0
        ws_manager.max_retries = 2
        ws_manager.state = ConnectionState.DISCONNECTED
        
        with patch.object(ws_manager, 'reconnect', return_value=False) as mock_reconnect:
            await ws_manager._auto_reconnect()
            
        assert mock_reconnect.call_count == 2  # max_retries
        assert ws_manager.state == ConnectionState.FAILED
        
    @pytest.mark.asyncio
    async def test_performance_many_messages(self, ws_manager):
        """Testa rendimiento con muchos mensajes."""
        import time
        
        # Crear 1000 mensajes
        messages = [
            json.dumps({"type": "latency", "data": {"value": i}, "timestamp": time.time()})
            for i in range(1000)
        ]
        
        mock_websocket = AsyncMock()
        mock_websocket.__aiter__ = AsyncMock(return_value=iter(messages))
        ws_manager.websocket = mock_websocket
        
        callback = MagicMock()
        ws_manager.subscribe(callback)
        
        start_time = time.time()
        await ws_manager._listen()
        end_time = time.time()
        
        # Verificar que se procesaron todos los mensajes
        assert callback.call_count == 1000
        
        # Verificar que el procesamiento fue rápido (< 1 segundo)
        processing_time = end_time - start_time
        assert processing_time < 1.0, f"Procesamiento demasiado lento: {processing_time}s"