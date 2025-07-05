"""Tests para State Manager y binding de eventos.

Testa la funcionalidad del StateManager, incluyendo el patrón Observer/Pub-Sub
y la latencia de notificación a listeners.
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from dataclasses import replace

from ui.state import (
    StateManager, BomberCatState, SystemStatus, LogLevel, LogEntry,
    LatencyPoint, DeviceInfo, FlashProgress
)


class TestStateManager:
    """Tests para la clase StateManager."""
    
    @pytest.fixture
    def state_manager(self):
        """Fixture que crea un StateManager para testing."""
        return StateManager()
        
    def test_initialization(self, state_manager):
        """Testa la inicialización del StateManager."""
        assert isinstance(state_manager.state, BomberCatState)
        assert state_manager.state.system_status == SystemStatus.IDLE
        assert not state_manager.state.relay_running
        assert state_manager.state.device_info is None
        assert state_manager.state.flash_progress is None
        assert len(state_manager.state.latency_data) == 0
        assert len(state_manager.state.logs) == 0
        assert state_manager.state.dark_theme
        assert not state_manager.state.websocket_connected
        assert state_manager._listeners == []
        
    def test_add_remove_listener(self, state_manager):
        """Testa agregar y remover listeners."""
        listener1 = MagicMock()
        listener2 = MagicMock()
        
        # Agregar listeners
        state_manager.add_listener(listener1)
        state_manager.add_listener(listener2)
        
        assert len(state_manager._listeners) == 2
        assert listener1 in state_manager._listeners
        assert listener2 in state_manager._listeners
        
        # No duplicar listeners
        state_manager.add_listener(listener1)
        assert len(state_manager._listeners) == 2
        
        # Remover listener
        state_manager.remove_listener(listener1)
        assert len(state_manager._listeners) == 1
        assert listener1 not in state_manager._listeners
        assert listener2 in state_manager._listeners
        
    def test_notify_listeners(self, state_manager):
        """Testa notificación a listeners."""
        listener1 = MagicMock()
        listener2 = MagicMock()
        
        state_manager.add_listener(listener1)
        state_manager.add_listener(listener2)
        
        # Cambiar estado
        state_manager.update_system_status(SystemStatus.RUNNING)
        
        # Verificar que se notificó a ambos listeners
        listener1.assert_called_once_with(state_manager.state)
        listener2.assert_called_once_with(state_manager.state)
        
    def test_notify_listeners_exception_handling(self, state_manager):
        """Testa manejo de excepciones en listeners."""
        failing_listener = MagicMock(side_effect=Exception("Test error"))
        working_listener = MagicMock()
        
        state_manager.add_listener(failing_listener)
        state_manager.add_listener(working_listener)
        
        # Cambiar estado (no debería lanzar excepción)
        state_manager.update_system_status(SystemStatus.RUNNING)
        
        # Ambos listeners deberían haberse llamado
        failing_listener.assert_called_once()
        working_listener.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_listener_notification_latency(self, state_manager):
        """Testa que los listeners reciban eventos en menos de 50ms."""
        notification_times = []
        
        def timing_listener(state):
            """Listener que registra el tiempo de notificación."""
            notification_times.append(time.time())
            
        state_manager.add_listener(timing_listener)
        
        # Realizar múltiples actualizaciones y medir latencia
        for i in range(10):
            start_time = time.time()
            state_manager.update_system_status(SystemStatus.RUNNING if i % 2 == 0 else SystemStatus.IDLE)
            
            # Permitir que el event loop procese
            await asyncio.sleep(0)
            
            # Calcular latencia
            if notification_times:
                latency_ms = (notification_times[-1] - start_time) * 1000
                assert latency_ms < 50, f"Latencia demasiado alta: {latency_ms:.2f}ms"
                
    def test_update_system_status(self, state_manager):
        """Testa actualización del estado del sistema."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        state_manager.update_system_status(SystemStatus.RUNNING)
        
        assert state_manager.state.system_status == SystemStatus.RUNNING
        listener.assert_called_once_with(state_manager.state)
        
    def test_update_device_info(self, state_manager):
        """Testa actualización de información del dispositivo."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        device_info = DeviceInfo(
            name="Test Device",
            port="/dev/ttyUSB0",
            chip_type="ESP32",
            mac_address="AA:BB:CC:DD:EE:FF"
        )
        
        state_manager.update_device_info(device_info)
        
        assert state_manager.state.device_info == device_info
        listener.assert_called_once_with(state_manager.state)
        
    def test_update_relay_status(self, state_manager):
        """Testa actualización del estado del relay."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        state_manager.update_relay_status(True)
        
        assert state_manager.state.relay_running is True
        listener.assert_called_once_with(state_manager.state)
        
    def test_update_flash_progress(self, state_manager):
        """Testa actualización del progreso de flash."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        flash_progress = FlashProgress(
            stage="Writing",
            percentage=75.5,
            current_step=3,
            total_steps=4,
            speed_kbps=256.0
        )
        
        state_manager.update_flash_progress(flash_progress)
        
        assert state_manager.state.flash_progress == flash_progress
        listener.assert_called_once_with(state_manager.state)
        
    def test_add_latency_point(self, state_manager):
        """Testa agregar punto de latencia."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        latency_point = LatencyPoint(timestamp=time.time(), latency_ms=25.5)
        state_manager.add_latency_point(latency_point)
        
        assert len(state_manager.state.latency_data) == 1
        assert state_manager.state.latency_data[0] == latency_point
        listener.assert_called_once_with(state_manager.state)
        
    def test_latency_buffer_limit(self, state_manager):
        """Testa límite del buffer de latencia (100 puntos)."""
        # Agregar 150 puntos de latencia
        for i in range(150):
            latency_point = LatencyPoint(timestamp=time.time() + i, latency_ms=float(i))
            state_manager.add_latency_point(latency_point)
            
        # Verificar que solo se mantienen los últimos 100
        assert len(state_manager.state.latency_data) == 100
        
        # Verificar que son los más recientes (latencia 50-149)
        latencies = [point.latency_ms for point in state_manager.state.latency_data]
        assert latencies == list(range(50, 150, 1))
        
    def test_add_log_entry(self, state_manager):
        """Testa agregar entrada de log."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        log_entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            message="Test message",
            source="test"
        )
        
        state_manager.add_log_entry(log_entry)
        
        assert len(state_manager.state.logs) == 1
        assert state_manager.state.logs[0] == log_entry
        listener.assert_called_once_with(state_manager.state)
        
    def test_log_buffer_limit(self, state_manager):
        """Testa límite del buffer de logs (500 entradas)."""
        # Agregar 600 entradas de log
        for i in range(600):
            log_entry = LogEntry(
                timestamp=time.time() + i,
                level=LogLevel.INFO,
                message=f"Message {i}",
                source="test"
            )
            state_manager.add_log_entry(log_entry)
            
        # Verificar que solo se mantienen las últimas 500
        assert len(state_manager.state.logs) == 500
        
        # Verificar que son las más recientes (mensaje 100-599)
        messages = [log.message for log in state_manager.state.logs]
        expected_messages = [f"Message {i}" for i in range(100, 600)]
        assert messages == expected_messages
        
    def test_clear_logs(self, state_manager):
        """Testa limpiar logs."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        # Agregar algunos logs
        for i in range(5):
            log_entry = LogEntry(
                timestamp=time.time(),
                level=LogLevel.INFO,
                message=f"Message {i}",
                source="test"
            )
            state_manager.add_log_entry(log_entry)
            
        assert len(state_manager.state.logs) == 5
        
        # Limpiar logs
        state_manager.clear_logs()
        
        assert len(state_manager.state.logs) == 0
        # Verificar que se notificó (6 llamadas: 5 add + 1 clear)
        assert listener.call_count == 6
        
    def test_toggle_theme(self, state_manager):
        """Testa cambio de tema."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        # Estado inicial: tema oscuro
        assert state_manager.state.dark_theme is True
        
        # Cambiar a tema claro
        state_manager.toggle_theme()
        
        assert state_manager.state.dark_theme is False
        listener.assert_called_once_with(state_manager.state)
        
        # Cambiar de vuelta a tema oscuro
        listener.reset_mock()
        state_manager.toggle_theme()
        
        assert state_manager.state.dark_theme is True
        listener.assert_called_once_with(state_manager.state)
        
    def test_update_websocket_status(self, state_manager):
        """Testa actualización del estado de WebSocket."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        state_manager.update_websocket_status(True)
        
        assert state_manager.state.websocket_connected is True
        listener.assert_called_once_with(state_manager.state)
        
    def test_update_performance_metrics(self, state_manager):
        """Testa actualización de métricas de rendimiento."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        metrics = {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 23.1,
            "network_rx": 1024.0,
            "network_tx": 512.0
        }
        
        state_manager.update_performance_metrics(metrics)
        
        assert state_manager.state.performance_metrics == metrics
        listener.assert_called_once_with(state_manager.state)
        
    @pytest.mark.asyncio
    async def test_concurrent_updates(self, state_manager):
        """Testa actualizaciones concurrentes del estado."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        async def update_status(status):
            """Función auxiliar para actualizar estado."""
            await asyncio.sleep(0.001)  # Simular trabajo asíncrono
            state_manager.update_system_status(status)
            
        async def update_relay(running):
            """Función auxiliar para actualizar relay."""
            await asyncio.sleep(0.001)
            state_manager.update_relay_status(running)
            
        # Ejecutar actualizaciones concurrentes
        await asyncio.gather(
            update_status(SystemStatus.RUNNING),
            update_relay(True),
            update_status(SystemStatus.IDLE),
            update_relay(False)
        )
        
        # Verificar que se llamó el listener para cada actualización
        assert listener.call_count == 4
        
    @pytest.mark.asyncio
    async def test_high_frequency_updates(self, state_manager):
        """Testa actualizaciones de alta frecuencia."""
        listener = MagicMock()
        state_manager.add_listener(listener)
        
        start_time = time.time()
        
        # Realizar 1000 actualizaciones rápidas
        for i in range(1000):
            latency_point = LatencyPoint(timestamp=time.time(), latency_ms=float(i % 100))
            state_manager.add_latency_point(latency_point)
            
            # Permitir que el event loop procese ocasionalmente
            if i % 100 == 0:
                await asyncio.sleep(0)
                
        end_time = time.time()
        
        # Verificar que se procesaron todas las actualizaciones
        assert listener.call_count == 1000
        
        # Verificar que el procesamiento fue rápido
        processing_time = end_time - start_time
        assert processing_time < 1.0, f"Procesamiento demasiado lento: {processing_time:.2f}s"
        
        # Verificar que el buffer se mantuvo en 100 elementos
        assert len(state_manager.state.latency_data) == 100
        
    def test_state_immutability(self, state_manager):
        """Testa que el estado se actualiza correctamente sin mutar el anterior."""
        # Obtener referencia al estado inicial
        initial_state = state_manager.state
        initial_status = initial_state.system_status
        
        # Actualizar estado
        state_manager.update_system_status(SystemStatus.RUNNING)
        
        # Verificar que el estado cambió
        assert state_manager.state.system_status == SystemStatus.RUNNING
        
        # Verificar que el estado inicial no se mutó
        assert initial_state.system_status == initial_status
        
        # Verificar que son objetos diferentes
        assert state_manager.state is not initial_state
        
    def test_multiple_state_managers(self):
        """Testa que múltiples StateManagers son independientes."""
        manager1 = StateManager()
        manager2 = StateManager()
        
        listener1 = MagicMock()
        listener2 = MagicMock()
        
        manager1.add_listener(listener1)
        manager2.add_listener(listener2)
        
        # Actualizar solo manager1
        manager1.update_system_status(SystemStatus.RUNNING)
        
        # Verificar que solo se notificó listener1
        listener1.assert_called_once()
        listener2.assert_not_called()
        
        # Verificar que los estados son independientes
        assert manager1.state.system_status == SystemStatus.RUNNING
        assert manager2.state.system_status == SystemStatus.IDLE