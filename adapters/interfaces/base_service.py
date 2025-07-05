"""Base service interfaces for BomberCat Integrator.

Define interfaces comunes para evitar dependencias circulares.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from enum import Enum


class ServiceStatus(Enum):
    """Estados posibles de un servicio."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class BaseService(ABC):
    """Interfaz base para todos los servicios."""
    
    def __init__(self):
        self._status = ServiceStatus.STOPPED
        self._error_message: Optional[str] = None
        
    @property
    def status(self) -> ServiceStatus:
        """Estado actual del servicio."""
        return self._status
        
    @property
    def error_message(self) -> Optional[str]:
        """Mensaje de error si el servicio está en estado ERROR."""
        return self._error_message
        
    @property
    def is_running(self) -> bool:
        """True si el servicio está ejecutándose."""
        return self._status == ServiceStatus.RUNNING
        
    @abstractmethod
    async def initialize(self) -> None:
        """Inicializa el servicio."""
        pass
        
    @abstractmethod
    async def start(self) -> None:
        """Inicia el servicio."""
        pass
        
    @abstractmethod
    async def stop(self) -> None:
        """Detiene el servicio."""
        pass
        
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verifica el estado de salud del servicio."""
        pass
        
    async def restart(self) -> None:
        """Reinicia el servicio."""
        await self.stop()
        await self.start()
        
    def _set_status(self, status: ServiceStatus, error_message: Optional[str] = None) -> None:
        """Establece el estado del servicio."""
        self._status = status
        self._error_message = error_message
        

class WebSocketManagerInterface(ABC):
    """Interfaz para el manager de WebSocket."""
    
    @abstractmethod
    async def connect(self, websocket) -> None:
        """Conecta un cliente WebSocket."""
        pass
        
    @abstractmethod
    async def disconnect(self, websocket) -> None:
        """Desconecta un cliente WebSocket."""
        pass
        
    @abstractmethod
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Envía un mensaje a todos los clientes conectados."""
        pass
        
    @abstractmethod
    async def broadcast_device_status(self, device_info: Dict[str, Any]) -> None:
        """Envía estado del dispositivo a todos los clientes."""
        pass
        
    @abstractmethod
    async def broadcast_flash_progress(self, progress: Dict[str, Any]) -> None:
        """Envía progreso de flasheo a todos los clientes."""
        pass
        
    @abstractmethod
    async def broadcast_latency(self, latency_ms: float) -> None:
        """Envía latencia del relay a todos los clientes."""
        pass
        
    @abstractmethod
    async def broadcast_metrics(self, metrics: Dict[str, Any]) -> None:
        """Envía métricas del sistema a todos los clientes."""
        pass
        
    @abstractmethod
    async def broadcast_logs(self, log_entry: Dict[str, Any]) -> None:
        """Envía logs a todos los clientes."""
        pass
        

class FlashServiceInterface(BaseService):
    """Interfaz para el servicio de flasheo."""
    
    @abstractmethod
    async def flash_device(
        self, 
        firmware_path: str, 
        device_port: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Flashea un dispositivo con el firmware especificado."""
        pass
        
    @abstractmethod
    async def detect_devices(self) -> List[Dict[str, Any]]:
        """Detecta dispositivos conectados."""
        pass
        
    @abstractmethod
    async def get_flash_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del proceso de flasheo."""
        pass
        
    @abstractmethod
    async def cancel_flash(self) -> bool:
        """Cancela el proceso de flasheo en curso."""
        pass
        

class ConfigServiceInterface(BaseService):
    """Interfaz para el servicio de configuración."""
    
    @abstractmethod
    async def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuración actual."""
        pass
        
    @abstractmethod
    async def update_config(self, config_data: Dict[str, Any]) -> bool:
        """Actualiza la configuración."""
        pass
        
    @abstractmethod
    async def backup_config(self) -> str:
        """Crea un backup de la configuración actual."""
        pass
        
    @abstractmethod
    async def restore_config(self, backup_id: str) -> bool:
        """Restaura una configuración desde backup."""
        pass
        
    @abstractmethod
    async def validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valida una configuración."""
        pass
        

class RelayServiceInterface(BaseService):
    """Interfaz para el servicio de relay TCP."""
    
    @abstractmethod
    async def start_relay(
        self, 
        source_port: int, 
        target_host: str, 
        target_port: int
    ) -> bool:
        """Inicia el relay TCP."""
        pass
        
    @abstractmethod
    async def stop_relay(self) -> bool:
        """Detiene el relay TCP."""
        pass
        
    @abstractmethod
    async def get_relay_status(self) -> Dict[str, Any]:
        """Obtiene el estado del relay."""
        pass
        
    @abstractmethod
    async def get_relay_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del relay."""
        pass
        

class MQTTServiceInterface(BaseService):
    """Interfaz para el servicio MQTT."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Conecta al broker MQTT."""
        pass
        
    @abstractmethod
    async def disconnect(self) -> bool:
        """Desconecta del broker MQTT."""
        pass
        
    @abstractmethod
    async def publish_telemetry(self, data: Dict[str, Any]) -> bool:
        """Publica datos de telemetría."""
        pass
        
    @abstractmethod
    async def publish_device_status(self, device_info: Dict[str, Any]) -> bool:
        """Publica estado del dispositivo."""
        pass
        
    @abstractmethod
    async def subscribe_commands(self, callback: callable) -> bool:
        """Se suscribe a comandos remotos."""
        pass
        
    @abstractmethod
    async def get_connection_status(self) -> Dict[str, Any]:
        """Obtiene el estado de la conexión MQTT."""
        pass