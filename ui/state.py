"""State Manager para el dashboard BomberCat.

Maneja el estado global de la aplicación usando patrón Observer/Pub-Sub
para notificar cambios a los componentes suscritos.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Optional
from enum import Enum
from datetime import datetime


class SystemStatus(Enum):
    """Estados del sistema BomberCat."""
    IDLE = "idle"
    FLASHING = "flashing"
    RELAY_RUNNING = "relay_running"
    ERROR = "error"
    CONNECTING = "connecting"


class LogLevel(Enum):
    """Niveles de log para el dashboard."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class LogEntry:
    """Entrada de log estructurada."""
    timestamp: datetime
    level: LogLevel
    message: str
    component: str = "system"


@dataclass
class LatencyPoint:
    """Punto de latencia para el gráfico."""
    timestamp: float
    latency_ms: float


@dataclass
class DeviceInfo:
    """Información del dispositivo conectado."""
    port: Optional[str] = None
    chip_type: Optional[str] = None
    mac_address: Optional[str] = None
    flash_size: Optional[str] = None
    connected: bool = False


@dataclass
class FlashProgress:
    """Progreso del proceso de flasheo."""
    current_step: str = ""
    progress_percent: float = 0.0
    total_steps: int = 0
    current_step_num: int = 0
    estimated_time_remaining: Optional[float] = None


@dataclass
class BomberCatState:
    """Estado global del sistema BomberCat."""
    # Estado del sistema
    status: SystemStatus = SystemStatus.IDLE
    
    # Información del dispositivo
    device: DeviceInfo = field(default_factory=DeviceInfo)
    
    # Estado del relay
    relay_running: bool = False
    relay_packets_sent: int = 0
    relay_packets_received: int = 0
    relay_errors: int = 0
    
    # Progreso de flasheo
    flash_progress: FlashProgress = field(default_factory=FlashProgress)
    
    # Datos de latencia (buffer circular de 100 puntos)
    latency_data: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Logs del sistema (buffer circular de 1000 entradas)
    logs: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Configuración del tema
    dark_theme: bool = True
    
    # Estado de conexión WebSocket
    websocket_connected: bool = False
    
    # Métricas de rendimiento
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    

class StateManager:
    """Manager del estado global con patrón Observer."""
    
    def __init__(self):
        """Inicializa el StateManager."""
        self.state = BomberCatState()
        self.listeners: Dict[str, List[Callable[[BomberCatState], None]]] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = asyncio.Lock()
        
    def add_listener(self, event_type: str, callback: Callable[[BomberCatState], None]):
        """Agrega un listener para un tipo de evento específico.
        
        Args:
            event_type: Tipo de evento ('status', 'device', 'relay', 'flash', 'latency', 'logs', 'all')
            callback: Función que será llamada cuando ocurra el evento
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []
            
        if callback not in self.listeners[event_type]:
            self.listeners[event_type].append(callback)
            self.logger.debug(f"Listener agregado para '{event_type}': {callback.__name__}")
            
    def remove_listener(self, event_type: str, callback: Callable[[BomberCatState], None]):
        """Remueve un listener.
        
        Args:
            event_type: Tipo de evento
            callback: Función a remover
        """
        if event_type in self.listeners and callback in self.listeners[event_type]:
            self.listeners[event_type].remove(callback)
            self.logger.debug(f"Listener removido para '{event_type}': {callback.__name__}")
            
    async def notify_listeners(self, event_type: str):
        """Notifica a todos los listeners de un tipo de evento.
        
        Args:
            event_type: Tipo de evento que ocurrió
        """
        # Notificar listeners específicos
        if event_type in self.listeners:
            for callback in self.listeners[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self.state)
                    else:
                        callback(self.state)
                except Exception as e:
                    self.logger.error(f"Error en listener {callback.__name__}: {e}")
                    
        # Notificar listeners globales
        if 'all' in self.listeners:
            for callback in self.listeners['all']:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self.state)
                    else:
                        callback(self.state)
                except Exception as e:
                    self.logger.error(f"Error en listener global {callback.__name__}: {e}")
                    
    async def update_status(self, status: SystemStatus):
        """Actualiza el estado del sistema."""
        async with self._lock:
            if self.state.status != status:
                old_status = self.state.status
                self.state.status = status
                self.logger.info(f"Estado cambiado: {old_status.value} -> {status.value}")
                await self.notify_listeners('status')
                
    async def update_device(self, device_info: DeviceInfo):
        """Actualiza información del dispositivo."""
        async with self._lock:
            self.state.device = device_info
            await self.notify_listeners('device')
            
    async def update_relay_status(self, running: bool, packets_sent: int = None, 
                                packets_received: int = None, errors: int = None):
        """Actualiza estado del relay."""
        async with self._lock:
            self.state.relay_running = running
            if packets_sent is not None:
                self.state.relay_packets_sent = packets_sent
            if packets_received is not None:
                self.state.relay_packets_received = packets_received
            if errors is not None:
                self.state.relay_errors = errors
            await self.notify_listeners('relay')
            
    async def update_flash_progress(self, progress: FlashProgress):
        """Actualiza progreso del flasheo."""
        async with self._lock:
            self.state.flash_progress = progress
            await self.notify_listeners('flash')
            
    async def add_latency_point(self, latency_ms: float):
        """Agrega un punto de latencia al buffer."""
        async with self._lock:
            point = LatencyPoint(
                timestamp=asyncio.get_event_loop().time(),
                latency_ms=latency_ms
            )
            self.state.latency_data.append(point)
            await self.notify_listeners('latency')
            
    async def add_log(self, level: LogLevel, message: str, component: str = "system"):
        """Agrega una entrada de log."""
        async with self._lock:
            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=level,
                message=message,
                component=component
            )
            self.state.logs.append(log_entry)
            await self.notify_listeners('logs')
            
    async def toggle_theme(self):
        """Alterna entre tema claro y oscuro."""
        async with self._lock:
            self.state.dark_theme = not self.state.dark_theme
            await self.notify_listeners('theme')
            
    async def update_websocket_status(self, connected: bool):
        """Actualiza estado de conexión WebSocket."""
        async with self._lock:
            if self.state.websocket_connected != connected:
                self.state.websocket_connected = connected
                status_msg = "conectado" if connected else "desconectado"
                await self.add_log(
                    LogLevel.INFO if connected else LogLevel.WARNING,
                    f"WebSocket {status_msg}",
                    "websocket"
                )
                await self.notify_listeners('websocket')
                
    async def update_metrics(self, cpu_usage: float, memory_usage: float):
        """Actualiza métricas de rendimiento."""
        async with self._lock:
            self.state.cpu_usage = cpu_usage
            self.state.memory_usage = memory_usage
            await self.notify_listeners('metrics')
            
    def get_state(self) -> BomberCatState:
        """Retorna una copia del estado actual."""
        return self.state
        
    async def reset_state(self):
        """Resetea el estado a valores por defecto."""
        async with self._lock:
            self.state = BomberCatState()
            await self.notify_listeners('all')
            

# Instancia global del StateManager
state_manager = StateManager()