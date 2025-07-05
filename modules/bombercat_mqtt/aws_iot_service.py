"""AWS IoT Service

Servicio MQTT para AWS IoT Core con reconexión automática y métricas.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable

try:
    from awscrt import mqtt
    from awsiot import mqtt_connection_builder
except ImportError:
    mqtt = None
    mqtt_connection_builder = None

from tenacity import retry, stop_after_attempt, wait_exponential


class ConnectionStatus(Enum):
    """Estados de conexión del servicio MQTT."""
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


@dataclass
class MQTTConfig:
    """Configuración para AWS IoT MQTT."""
    endpoint: str
    cert_path: str
    key_path: str
    ca_path: str
    client_id: Optional[str] = None
    device_id: Optional[str] = None
    
    def __post_init__(self):
        if self.client_id is None:
            self.client_id = f"bombercat-{uuid.uuid4().hex[:8]}"
        if self.device_id is None:
            self.device_id = self.client_id


class AWSIoTService:
    """Servicio AWS IoT Core con MQTT + TLS.
    
    Características:
    - Reconexión automática con back-off exponencial
    - QoS 1 (AT_LEAST_ONCE)
    - Métricas de estado
    - Keepalive automático
    """
    
    # Tópicos MQTT
    TELEMETRY_TOPIC = "bombercat/telemetry"
    EVENTS_TOPIC = "bombercat/events"
    
    # Configuración
    MAX_RECONNECT_ATTEMPTS = 5
    KEEPALIVE_INTERVAL = 25  # segundos
    QOS = mqtt.QoS.AT_LEAST_ONCE if mqtt else 1
    
    def __init__(self, config: MQTTConfig):
        """Inicializa el servicio AWS IoT.
        
        Args:
            config: Configuración MQTT
        """
        if mqtt is None:
            raise ImportError(
                "awscrt y awsiot son requeridos. Instalar con: pip install awscrt awsiot"
            )
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Estado de conexión
        self._status = ConnectionStatus.STOPPED
        self._connection: Optional[mqtt.Connection] = None
        self._reconnect_attempts = 0
        self._last_publish_ts: Optional[float] = None
        
        # Tareas asíncronas
        self._keepalive_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_connection_interrupted: Optional[Callable] = None
        self._on_connection_resumed: Optional[Callable] = None
        
        # Crear conexión MQTT
        self._create_connection()
    
    @classmethod
    def from_env(cls, device_id: Optional[str] = None) -> 'AWSIoTService':
        """Crea servicio desde variables de entorno.
        
        Variables esperadas:
        - AWS_IOT_ENDPOINT
        - AWS_IOT_CERT_PATH
        - AWS_IOT_KEY_PATH
        - AWS_IOT_CA_PATH
        - AWS_IOT_CLIENT_ID (opcional)
        
        Args:
            device_id: ID del dispositivo (opcional)
            
        Returns:
            Instancia del servicio
            
        Raises:
            ValueError: Si faltan variables de entorno
        """
        required_vars = [
            "AWS_IOT_ENDPOINT",
            "AWS_IOT_CERT_PATH", 
            "AWS_IOT_KEY_PATH",
            "AWS_IOT_CA_PATH"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Variables de entorno faltantes: {missing_vars}")
        
        config = MQTTConfig(
            endpoint=os.getenv("AWS_IOT_ENDPOINT"),
            cert_path=os.getenv("AWS_IOT_CERT_PATH"),
            key_path=os.getenv("AWS_IOT_KEY_PATH"),
            ca_path=os.getenv("AWS_IOT_CA_PATH"),
            client_id=os.getenv("AWS_IOT_CLIENT_ID"),
            device_id=device_id
        )
        
        return cls(config)
    
    def _create_connection(self):
        """Crea la conexión MQTT con AWS IoT."""
        try:
            self._connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.config.endpoint,
                cert_filepath=self.config.cert_path,
                pri_key_filepath=self.config.key_path,
                ca_filepath=self.config.ca_path,
                client_id=self.config.client_id,
                clean_session=False,
                keep_alive_secs=30,
                on_connection_interrupted=self._on_connection_interrupted_callback,
                on_connection_resumed=self._on_connection_resumed_callback
            )
            
            self.logger.info(f"Conexión MQTT creada para cliente {self.config.client_id}")
            
        except Exception as e:
            self.logger.error(f"Error creando conexión MQTT: {e}")
            raise
    
    def _on_connection_interrupted_callback(self, connection, error, **kwargs):
        """Callback cuando la conexión se interrumpe."""
        self.logger.warning(f"Conexión MQTT interrumpida: {error}")
        self._status = ConnectionStatus.DISCONNECTED
        
        # Iniciar reconexión automática
        if self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            try:
                # Verificar si hay un loop de eventos corriendo
                loop = asyncio.get_running_loop()
                self._reconnect_task = loop.create_task(self._reconnect_with_backoff())
            except RuntimeError:
                # No hay loop corriendo, probablemente en tests
                self.logger.debug("No hay loop de eventos corriendo para reconexión")
    
    def _on_connection_resumed_callback(self, connection, return_code, session_present, **kwargs):
        """Callback cuando la conexión se restablece."""
        self.logger.info(f"Conexión MQTT restablecida: {return_code}")
        self._status = ConnectionStatus.CONNECTED
        self._reconnect_attempts = 0
    
    async def start(self) -> bool:
        """Inicia el servicio MQTT.
        
        Returns:
            True si la conexión fue exitosa
        """
        if self._status != ConnectionStatus.STOPPED:
            self.logger.warning("Servicio ya iniciado")
            return True
        
        try:
            self._status = ConnectionStatus.CONNECTING
            self.logger.info("Iniciando servicio AWS IoT MQTT...")
            
            # Conectar
            connect_future = self._connection.connect()
            await asyncio.wrap_future(connect_future)
            
            self._status = ConnectionStatus.CONNECTED
            self._reconnect_attempts = 0
            
            # Iniciar keepalive
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            
            # Publicar evento de conexión
            await self.publish_event("connection", {"status": "online"})
            
            self.logger.info("Servicio AWS IoT MQTT iniciado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error iniciando servicio MQTT: {e}")
            self._status = ConnectionStatus.STOPPED
            return False
    
    async def stop(self):
        """Detiene el servicio MQTT."""
        if self._status == ConnectionStatus.STOPPED:
            return
        
        self.logger.info("Deteniendo servicio AWS IoT MQTT...")
        
        try:
            # Publicar evento de desconexión
            if self._status == ConnectionStatus.CONNECTED:
                await self.publish_event("connection", {"status": "offline"})
            
            # Cancelar tareas
            if self._keepalive_task:
                self._keepalive_task.cancel()
                try:
                    await self._keepalive_task
                except asyncio.CancelledError:
                    pass
            
            if self._reconnect_task:
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass
            
            # Desconectar
            if self._connection:
                disconnect_future = self._connection.disconnect()
                await asyncio.wrap_future(disconnect_future)
            
            self._status = ConnectionStatus.STOPPED
            self.logger.info("Servicio AWS IoT MQTT detenido")
            
        except Exception as e:
            self.logger.error(f"Error deteniendo servicio MQTT: {e}")
            self._status = ConnectionStatus.STOPPED
    
    @retry(
        stop=stop_after_attempt(MAX_RECONNECT_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=32)
    )
    async def _reconnect_with_backoff(self):
        """Reconecta con back-off exponencial."""
        if self._status == ConnectionStatus.STOPPED:
            return
        
        self._reconnect_attempts += 1
        self._status = ConnectionStatus.RECONNECTING
        
        self.logger.info(f"Intento de reconexión {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS}")
        
        try:
            # Intentar reconectar
            connect_future = self._connection.connect()
            await asyncio.wrap_future(connect_future)
            
            self._status = ConnectionStatus.CONNECTED
            self._reconnect_attempts = 0
            
            self.logger.info("Reconexión exitosa")
            
        except Exception as e:
            self.logger.error(f"Error en reconexión: {e}")
            
            if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
                self.logger.error("Máximo de intentos de reconexión alcanzado")
                self._status = ConnectionStatus.STOPPED
                raise
            
            # Esperar antes del siguiente intento
            wait_time = 2 ** self._reconnect_attempts
            self.logger.info(f"Esperando {wait_time}s antes del siguiente intento")
            await asyncio.sleep(wait_time)
            raise  # Para que tenacity maneje el retry
    
    async def publish_telemetry(self, data: Dict[str, Any]) -> bool:
        """Publica datos de telemetría.
        
        Args:
            data: Datos de telemetría
            
        Returns:
            True si la publicación fue exitosa
        """
        payload = {
            "timestamp": time.time(),
            "device_id": self.config.device_id,
            "data": data
        }
        
        return await self._publish(self.TELEMETRY_TOPIC, payload)
    
    async def publish_event(self, event: str, metadata: Dict[str, Any]) -> bool:
        """Publica un evento.
        
        Args:
            event: Tipo de evento
            metadata: Metadatos del evento
            
        Returns:
            True si la publicación fue exitosa
        """
        payload = {
            "timestamp": time.time(),
            "device_id": self.config.device_id,
            "event": event,
            "metadata": metadata
        }
        
        return await self._publish(self.EVENTS_TOPIC, payload)
    
    async def _publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Publica un mensaje MQTT.
        
        Args:
            topic: Tópico MQTT
            payload: Payload del mensaje
            
        Returns:
            True si la publicación fue exitosa
        """
        if self._status != ConnectionStatus.CONNECTED:
            self.logger.warning(f"No se puede publicar: estado {self._status.value}")
            return False
        
        try:
            message = json.dumps(payload, ensure_ascii=False)
            
            publish_future = self._connection.publish(
                topic=topic,
                payload=message,
                qos=self.QOS
            )
            
            # Esperar confirmación (QoS 1)
            await asyncio.wrap_future(publish_future)
            
            self._last_publish_ts = time.time()
            self.logger.debug(f"Mensaje publicado en {topic}: {len(message)} bytes")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error publicando en {topic}: {e}")
            return False
    
    async def _keepalive_loop(self):
        """Bucle de keepalive."""
        while self._status == ConnectionStatus.CONNECTED:
            try:
                await asyncio.sleep(self.KEEPALIVE_INTERVAL)
                
                # Enviar ping de keepalive
                await self.publish_event("keepalive", {
                    "uptime": time.time(),
                    "status": "alive"
                })
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error en keepalive: {e}")
                break
    
    def status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del servicio.
        
        Returns:
            Diccionario con métricas de estado
        """
        return {
            "connection_status": self._status.value,
            "connected": self._status == ConnectionStatus.CONNECTED,
            "reconnect_attempts": self._reconnect_attempts,
            "last_publish_ts": self._last_publish_ts,
            "client_id": self.config.client_id,
            "device_id": self.config.device_id,
            "endpoint": self.config.endpoint
        }
    
    @property
    def connection_status(self) -> ConnectionStatus:
        """Estado de conexión actual."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """True si está conectado."""
        return self._status == ConnectionStatus.CONNECTED
    
    def __repr__(self) -> str:
        return f"AWSIoTService(client_id={self.config.client_id}, status={self._status.value})"