"""MQTT service para comunicación con brokers MQTT."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class MQTTService:
    """Servicio para comunicación MQTT."""
    
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883):
        """Inicializar el servicio MQTT.
        
        Args:
            broker_host: Host del broker MQTT
            broker_port: Puerto del broker MQTT
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.is_connected = False
        self.client_id = "bombercat_integrator"
        self.subscriptions: Dict[str, Callable] = {}
        self.connection_task: Optional[asyncio.Task] = None
        logger.info(f"MQTTService inicializado: {broker_host}:{broker_port}")
    
    async def connect(self) -> bool:
        """Conecta al broker MQTT.
        
        Returns:
            True si la conexión fue exitosa
        """
        try:
            logger.info(f"Conectando a MQTT broker: {self.broker_host}:{self.broker_port}")
            
            # Simular conexión MQTT
            await asyncio.sleep(0.5)  # Simular tiempo de conexión
            
            self.is_connected = True
            self.connection_task = asyncio.create_task(self._maintain_connection())
            
            logger.info("Conectado exitosamente al broker MQTT")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a MQTT: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> bool:
        """Desconecta del broker MQTT.
        
        Returns:
            True si la desconexión fue exitosa
        """
        try:
            logger.info("Desconectando de MQTT broker")
            
            if self.connection_task:
                self.connection_task.cancel()
                try:
                    await self.connection_task
                except asyncio.CancelledError:
                    pass
                self.connection_task = None
            
            self.is_connected = False
            self.subscriptions.clear()
            
            logger.info("Desconectado exitosamente del broker MQTT")
            return True
            
        except Exception as e:
            logger.error(f"Error desconectando de MQTT: {e}")
            return False
    
    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> bool:
        """Publica un mensaje en un topic MQTT.
        
        Args:
            topic: Topic MQTT
            payload: Datos a publicar
            qos: Quality of Service (0, 1, 2)
            
        Returns:
            True si la publicación fue exitosa
        """
        try:
            if not self.is_connected:
                logger.warning("No conectado a MQTT, no se puede publicar")
                return False
            
            message = json.dumps(payload)
            logger.debug(f"Publicando en {topic}: {message}")
            
            # Simular publicación
            await asyncio.sleep(0.01)  # Simular latencia de red
            
            return True
            
        except Exception as e:
            logger.error(f"Error publicando en MQTT: {e}")
            return False
    
    async def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], None]) -> bool:
        """Se suscribe a un topic MQTT.
        
        Args:
            topic: Topic MQTT
            callback: Función a llamar cuando se reciba un mensaje
            
        Returns:
            True si la suscripción fue exitosa
        """
        try:
            if not self.is_connected:
                logger.warning("No conectado a MQTT, no se puede suscribir")
                return False
            
            self.subscriptions[topic] = callback
            logger.info(f"Suscrito a topic: {topic}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error suscribiéndose a MQTT: {e}")
            return False
    
    async def unsubscribe(self, topic: str) -> bool:
        """Se desuscribe de un topic MQTT.
        
        Args:
            topic: Topic MQTT
            
        Returns:
            True si la desuscripción fue exitosa
        """
        try:
            if topic in self.subscriptions:
                del self.subscriptions[topic]
                logger.info(f"Desuscrito de topic: {topic}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error desuscribiéndose de MQTT: {e}")
            return False
    
    async def publish_telemetry(self, telemetry_data: Dict[str, Any]) -> bool:
        """Publica datos de telemetría.
        
        Args:
            telemetry_data: Datos de telemetría
            
        Returns:
            True si la publicación fue exitosa
        """
        topic = f"bombercat/{self.client_id}/telemetry"
        return await self.publish(topic, telemetry_data)
    
    async def publish_device_status(self, device_status: Dict[str, Any]) -> bool:
        """Publica estado del dispositivo.
        
        Args:
            device_status: Estado del dispositivo
            
        Returns:
            True si la publicación fue exitosa
        """
        topic = f"bombercat/{self.client_id}/device/status"
        return await self.publish(topic, device_status)
    
    async def publish_relay_metrics(self, relay_metrics: Dict[str, Any]) -> bool:
        """Publica métricas del relay.
        
        Args:
            relay_metrics: Métricas del relay
            
        Returns:
            True si la publicación fue exitosa
        """
        topic = f"bombercat/{self.client_id}/relay/metrics"
        return await self.publish(topic, relay_metrics)
    
    async def _maintain_connection(self):
        """Mantiene la conexión MQTT activa."""
        try:
            while self.is_connected:
                # Simular heartbeat
                await asyncio.sleep(30.0)  # Heartbeat cada 30 segundos
                
                if self.is_connected:
                    logger.debug("MQTT heartbeat")
                    
        except asyncio.CancelledError:
            logger.info("Mantenimiento de conexión MQTT cancelado")
        except Exception as e:
            logger.error(f"Error manteniendo conexión MQTT: {e}")
            self.is_connected = False
    
    def is_connected(self) -> bool:
        """Verifica si está conectado al broker MQTT."""
        return self.is_connected
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado del servicio MQTT."""
        return {
            "connected": self.is_connected,
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "client_id": self.client_id,
            "subscriptions": list(self.subscriptions.keys())
        }