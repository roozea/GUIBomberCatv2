"""WebSocket Manager para comunicación en tiempo real con el backend.

Este módulo maneja la conexión WebSocket con reconexión automática
y distribución de mensajes a los suscriptores.
"""

import asyncio
import json
import logging
from typing import Callable, Optional, Any, Dict
from dataclasses import dataclass
from enum import Enum

import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI


class ConnectionState(Enum):
    """Estados de conexión del WebSocket."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class WSMessage:
    """Mensaje WebSocket estructurado."""
    type: str
    data: Dict[str, Any]
    timestamp: float


class WSManager:
    """Manager para conexiones WebSocket con reconexión automática."""
    
    def __init__(self, url: str, max_retries: int = 5):
        """Inicializa el WebSocket Manager.
        
        Args:
            url: URL del WebSocket (ej: ws://localhost:8000/ws)
            max_retries: Número máximo de reintentos de conexión
        """
        self.url = url
        self.max_retries = max_retries
        self.state = ConnectionState.DISCONNECTED
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.subscribers: list[Callable[[WSMessage], None]] = []
        self.retry_count = 0
        self.reconnect_task: Optional[asyncio.Task] = None
        self.listen_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(__name__)
        
    @property
    def connected(self) -> bool:
        """Retorna True si está conectado."""
        return self.state == ConnectionState.CONNECTED
        
    async def connect(self) -> bool:
        """Establece conexión WebSocket.
        
        Returns:
            True si la conexión fue exitosa, False en caso contrario
        """
        if self.state == ConnectionState.CONNECTED:
            return True
            
        self.state = ConnectionState.CONNECTING
        self.logger.info(f"Conectando a {self.url}...")
        
        try:
            self.websocket = await websockets.connect(
                self.url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            self.state = ConnectionState.CONNECTED
            self.retry_count = 0
            self.logger.info("Conexión WebSocket establecida")
            
            # Iniciar tarea de escucha
            self.listen_task = asyncio.create_task(self._listen())
            
            return True
            
        except (ConnectionClosed, InvalidURI, OSError) as e:
            self.logger.error(f"Error conectando WebSocket: {e}")
            self.state = ConnectionState.DISCONNECTED
            return False
            
    async def disconnect(self):
        """Desconecta el WebSocket y cancela tareas."""
        self.logger.info("Desconectando WebSocket...")
        
        # Cancelar tareas
        if self.listen_task and not self.listen_task.done():
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
                
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
        
        # Cerrar WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        self.state = ConnectionState.DISCONNECTED
        self.logger.info("WebSocket desconectado")
        
    async def send(self, message: Dict[str, Any]) -> bool:
        """Envía un mensaje por WebSocket.
        
        Args:
            message: Diccionario con el mensaje a enviar
            
        Returns:
            True si el mensaje fue enviado, False en caso contrario
        """
        if not self.connected or not self.websocket:
            self.logger.warning("Intento de envío sin conexión activa")
            return False
            
        try:
            await self.websocket.send(json.dumps(message))
            self.logger.debug(f"Mensaje enviado: {message}")
            return True
            
        except (ConnectionClosed, OSError) as e:
            self.logger.error(f"Error enviando mensaje: {e}")
            await self._handle_disconnect()
            return False
            
    def subscribe(self, callback: Callable[[WSMessage], None]):
        """Suscribe un callback para recibir mensajes.
        
        Args:
            callback: Función que será llamada con cada mensaje recibido
        """
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            self.logger.debug(f"Suscriptor agregado: {callback.__name__}")
            
    def unsubscribe(self, callback: Callable[[WSMessage], None]):
        """Desuscribe un callback.
        
        Args:
            callback: Función a desuscribir
        """
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            self.logger.debug(f"Suscriptor removido: {callback.__name__}")
            
    async def reconnect(self) -> bool:
        """Intenta reconectar con backoff exponencial.
        
        Returns:
            True si la reconexión fue exitosa
        """
        if self.retry_count >= self.max_retries:
            self.logger.error(f"Máximo de reintentos alcanzado ({self.max_retries})")
            self.state = ConnectionState.FAILED
            return False
            
        self.state = ConnectionState.RECONNECTING
        self.retry_count += 1
        
        # Backoff exponencial: 1s, 2s, 4s, 8s, 16s
        delay = min(2 ** (self.retry_count - 1), 16)
        self.logger.info(f"Reintento {self.retry_count}/{self.max_retries} en {delay}s")
        
        await asyncio.sleep(delay)
        return await self.connect()
        
    async def _listen(self):
        """Tarea de escucha de mensajes WebSocket."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    ws_message = WSMessage(
                        type=data.get('type', 'unknown'),
                        data=data.get('data', {}),
                        timestamp=data.get('timestamp', asyncio.get_event_loop().time())
                    )
                    
                    # Notificar a todos los suscriptores
                    for callback in self.subscribers:
                        try:
                            callback(ws_message)
                        except Exception as e:
                            self.logger.error(f"Error en callback {callback.__name__}: {e}")
                            
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error decodificando mensaje JSON: {e}")
                    
        except ConnectionClosed:
            self.logger.warning("Conexión WebSocket cerrada")
            await self._handle_disconnect()
        except Exception as e:
            self.logger.error(f"Error inesperado en _listen: {e}")
            await self._handle_disconnect()
            
    async def _handle_disconnect(self):
        """Maneja desconexiones inesperadas."""
        if self.state == ConnectionState.CONNECTED:
            self.logger.warning("Desconexión inesperada, iniciando reconexión...")
            self.state = ConnectionState.DISCONNECTED
            
            # Iniciar reconexión automática
            if not self.reconnect_task or self.reconnect_task.done():
                self.reconnect_task = asyncio.create_task(self._auto_reconnect())
                
    async def _auto_reconnect(self):
        """Tarea de reconexión automática."""
        while self.retry_count < self.max_retries and self.state != ConnectionState.CONNECTED:
            if await self.reconnect():
                break
                
        if self.state != ConnectionState.CONNECTED:
            self.logger.error("Reconexión automática falló")
            self.state = ConnectionState.FAILED