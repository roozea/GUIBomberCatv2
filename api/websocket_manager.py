"""WebSocket Connection Manager para BomberCat Integrator."""

import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Gestor de conexiones WebSocket para broadcast de mensajes."""
    
    def __init__(self):
        """Inicializa el gestor de conexiones."""
        self.active_connections: List[WebSocket] = []
        self.logger = logging.getLogger(__name__)
        
    async def connect(self, websocket: WebSocket) -> None:
        """Acepta una nueva conexión WebSocket.
        
        Args:
            websocket: Conexión WebSocket a aceptar
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"Nueva conexión WebSocket. Total: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket) -> None:
        """Desconecta y remueve una conexión WebSocket.
        
        Args:
            websocket: Conexión WebSocket a remover
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.logger.info(f"Conexión WebSocket desconectada. Total: {len(self.active_connections)}")
            
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Envía un mensaje a una conexión específica.
        
        Args:
            message: Mensaje a enviar
            websocket: Conexión WebSocket destino
        """
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            self.logger.error(f"Error enviando mensaje personal: {e}")
            self.disconnect(websocket)
            
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Envía un mensaje a todas las conexiones activas.
        
        Args:
            message: Mensaje a broadcast
        """
        if not self.active_connections:
            return
            
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                self.logger.error(f"Error en broadcast a conexión: {e}")
                disconnected.append(connection)
                
        # Limpiar conexiones desconectadas
        for connection in disconnected:
            self.disconnect(connection)
            
    async def broadcast_device_status(self, device_info: Dict[str, Any]) -> None:
        """Broadcast del estado del dispositivo.
        
        Args:
            device_info: Información del dispositivo
        """
        message = {
            "type": "device_info",
            "data": device_info,
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    async def broadcast_flash_progress(self, progress_data: Dict[str, Any]) -> None:
        """Broadcast del progreso de flasheo.
        
        Args:
            progress_data: Datos del progreso
        """
        message = {
            "type": "flash_progress",
            "data": progress_data,
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    async def broadcast_system_status(self, status: str) -> None:
        """Broadcast del estado del sistema.
        
        Args:
            status: Estado del sistema
        """
        message = {
            "type": "system_status",
            "data": {"status": status},
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    async def broadcast_log(self, level: str, message_text: str, source: str = "api") -> None:
        """Broadcast de un log del sistema.
        
        Args:
            level: Nivel del log (INFO, WARNING, ERROR)
            message_text: Mensaje del log
            source: Fuente del log
        """
        message = {
            "type": "log",
            "data": {
                "level": level,
                "message": message_text,
                "source": source
            },
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    async def broadcast_latency(self, latency_ms: float) -> None:
        """Broadcast de latencia del relay.
        
        Args:
            latency_ms: Latencia en milisegundos
        """
        message = {
            "type": "latency",
            "data": {"latency": latency_ms},
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    async def broadcast_relay_status(self, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Broadcast del estado del relay.
        
        Args:
            status: Estado del relay (running, stopped, error)
            details: Detalles adicionales del estado
        """
        message = {
            "type": "relay_status",
            "data": {
                "status": status,
                "details": details or {}
            },
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    async def broadcast_metrics(self, metrics: Dict[str, Any]) -> None:
        """Broadcast de métricas del sistema.
        
        Args:
            metrics: Métricas del sistema
        """
        message = {
            "type": "metrics",
            "data": metrics,
            "timestamp": self._get_timestamp()
        }
        await self.broadcast(message)
        
    def get_connection_count(self) -> int:
        """Retorna el número de conexiones activas.
        
        Returns:
            Número de conexiones activas
        """
        return len(self.active_connections)
        
    def _get_timestamp(self) -> str:
        """Genera timestamp actual en formato ISO.
        
        Returns:
            Timestamp en formato ISO
        """
        from datetime import datetime
        return datetime.now().isoformat()