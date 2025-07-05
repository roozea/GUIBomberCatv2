"""MQTT service API routes.

Endpoints para gestión de conexiones y mensajería MQTT.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from api.dependencies import get_mqtt_service
from adapters.interfaces import MQTTServiceInterface


router = APIRouter()


class MQTTMessage(BaseModel):
    """Model para mensajes MQTT."""
    topic: str
    payload: str
    qos: Optional[int] = 0
    retain: Optional[bool] = False


class MQTTSubscription(BaseModel):
    """Model para suscripciones MQTT."""
    topic: str
    qos: Optional[int] = 0
    callback_url: Optional[str] = None  # URL para webhook cuando se reciba mensaje


class MQTTConnectionInfo(BaseModel):
    """Information about MQTT connection."""
    broker_host: str
    broker_port: int
    client_id: str
    username: Optional[str] = None
    connected: bool
    last_connect: Optional[str] = None
    last_disconnect: Optional[str] = None


class MQTTTopicInfo(BaseModel):
    """Information about MQTT topics."""
    topic: str
    subscribed: bool
    qos: int
    message_count: int
    last_message: Optional[str] = None


@router.get("/status", response_model=MQTTConnectionInfo)
async def get_mqtt_status(
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
) -> MQTTConnectionInfo:
    """Obtiene el estado de la conexión MQTT."""
    try:
        status = await mqtt_service.get_connection_status()
        return MQTTConnectionInfo(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting MQTT status: {str(e)}")


@router.post("/connect", response_model=dict)
async def connect_mqtt(
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Establece conexión con el broker MQTT."""
    try:
        result = await mqtt_service.connect()
        return {
            "message": "MQTT connection established",
            "connected": result.get("connected", False),
            "broker": result.get("broker")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to MQTT: {str(e)}")


@router.post("/disconnect", response_model=dict)
async def disconnect_mqtt(
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Desconecta del broker MQTT."""
    try:
        await mqtt_service.disconnect()
        return {"message": "MQTT disconnected successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error disconnecting MQTT: {str(e)}")


@router.post("/publish", response_model=dict)
async def publish_message(
    message: MQTTMessage,
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Publica un mensaje en un topic MQTT."""
    try:
        result = await mqtt_service.publish(
            message.topic,
            message.payload,
            message.qos,
            message.retain
        )
        
        return {
            "message": "Message published successfully",
            "topic": message.topic,
            "payload_size": len(message.payload),
            "qos": message.qos,
            "message_id": result.get("message_id")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error publishing message: {str(e)}")


@router.post("/subscribe", response_model=dict)
async def subscribe_topic(
    subscription: MQTTSubscription,
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Se suscribe a un topic MQTT."""
    try:
        result = await mqtt_service.subscribe(
            subscription.topic,
            subscription.qos,
            subscription.callback_url
        )
        
        return {
            "message": "Subscribed successfully",
            "topic": subscription.topic,
            "qos": subscription.qos,
            "subscription_id": result.get("subscription_id")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subscribing to topic: {str(e)}")


@router.delete("/subscribe/{topic:path}", response_model=dict)
async def unsubscribe_topic(
    topic: str,
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Se desuscribe de un topic MQTT."""
    try:
        await mqtt_service.unsubscribe(topic)
        return {
            "message": "Unsubscribed successfully",
            "topic": topic
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unsubscribing from topic: {str(e)}")


@router.get("/subscriptions", response_model=List[MQTTTopicInfo])
async def list_subscriptions(
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
) -> List[MQTTTopicInfo]:
    """Lista todas las suscripciones activas."""
    try:
        subscriptions = await mqtt_service.list_subscriptions()
        return [MQTTTopicInfo(**sub) for sub in subscriptions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing subscriptions: {str(e)}")


@router.get("/messages/{topic:path}", response_model=List[Dict[str, Any]])
async def get_topic_messages(
    topic: str,
    limit: Optional[int] = 100,
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
) -> List[Dict[str, Any]]:
    """Obtiene mensajes recientes de un topic."""
    try:
        messages = await mqtt_service.get_topic_messages(topic, limit)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting messages: {str(e)}")


@router.get("/topics", response_model=List[str])
async def discover_topics(
    pattern: Optional[str] = None,
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
) -> List[str]:
    """Descubre topics disponibles en el broker."""
    try:
        topics = await mqtt_service.discover_topics(pattern)
        return topics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error discovering topics: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_mqtt_metrics(
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
) -> Dict[str, Any]:
    """Obtiene métricas del servicio MQTT."""
    try:
        metrics = await mqtt_service.get_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting MQTT metrics: {str(e)}")


@router.post("/config", response_model=dict)
async def update_mqtt_config(
    config: Dict[str, Any],
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Actualiza la configuración MQTT."""
    try:
        result = await mqtt_service.update_config(config)
        return {
            "message": "MQTT configuration updated",
            "config": result.get("config"),
            "restart_required": result.get("restart_required", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating MQTT config: {str(e)}")


@router.get("/config", response_model=Dict[str, Any])
async def get_mqtt_config(
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
) -> Dict[str, Any]:
    """Obtiene la configuración actual de MQTT."""
    try:
        config = await mqtt_service.get_config()
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting MQTT config: {str(e)}")


@router.post("/test", response_model=dict)
async def test_mqtt_connection(
    broker_config: Optional[Dict[str, Any]] = None,
    mqtt_service: MQTTServiceInterface = Depends(get_mqtt_service)
):
    """Prueba la conexión MQTT con configuración opcional."""
    try:
        result = await mqtt_service.test_connection(broker_config)
        return {
            "connection_test": "success" if result.get("connected") else "failed",
            "latency_ms": result.get("latency_ms"),
            "broker_info": result.get("broker_info"),
            "error": result.get("error")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing MQTT connection: {str(e)}")