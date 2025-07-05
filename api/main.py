"""Main FastAPI application for BomberCat Integrator.

Implementa el backend completo con WebSocket, REST endpoints y tareas background.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.websocket_manager import ConnectionManager
from api.routes import register_routes
from services.flash_service import FlashService
from services.config_service import ConfigService
from services.relay_service import RelayService
from services.mqtt_service import MQTTService


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Modelos Pydantic para requests
class FlashRequest(BaseModel):
    """Request para flashear dispositivo."""
    firmware_url: Optional[str] = None
    firmware_path: Optional[str] = None
    device_port: Optional[str] = None
    
class ConfigRequest(BaseModel):
    """Request para configuración."""
    config_data: Dict[str, Any]
    
class RelayCommand(BaseModel):
    """Comando para el relay."""
    action: str  # start, stop
    
class RelayCommandRequest(BaseModel):
    """Request para comandos del relay."""
    source_port: int
    target_host: str
    target_port: int
    
class WebSocketCommand(BaseModel):
    """Comando recibido via WebSocket."""
    cmd: str
    data: Optional[Dict[str, Any]] = None


# Variables globales para servicios y estado
connection_manager = ConnectionManager()
flash_service: Optional[FlashService] = None
config_service: Optional[ConfigService] = None
relay_service: Optional[RelayService] = None
mqtt_service: Optional[MQTTService] = None
background_tasks_running = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager - inicializa y limpia servicios."""
    global flash_service, config_service, relay_service, mqtt_service, background_tasks_running
    
    logger.info("🚀 Iniciando BomberCat Integrator API")
    
    try:
        # Inicializar servicios (9.3)
        flash_service = FlashService()
        config_service = ConfigService()
        relay_service = RelayService()
        mqtt_service = MQTTService()
        
        # Conectar MQTT service
        try:
            await mqtt_service.connect()
            logger.info("✅ MQTT service conectado")
        except Exception as e:
            logger.warning(f"⚠️ MQTT service no disponible: {e}")
            
        # Iniciar tareas background (9.5)
        background_tasks_running = True
        asyncio.create_task(monitor_device_status())
        asyncio.create_task(relay_metrics_publisher())
        logger.info("✅ Tareas background iniciadas")
        
        # Almacenar en app state
        app.state.connection_manager = connection_manager
        app.state.flash_service = flash_service
        app.state.config_service = config_service
        app.state.relay_service = relay_service
        app.state.mqtt_service = mqtt_service
        
        logger.info("✅ Todos los servicios iniciados correctamente")
        
        yield
        
    finally:
        # Cleanup
        logger.info("🛑 Cerrando BomberCat Integrator API")
        background_tasks_running = False
        
        if mqtt_service:
            try:
                await mqtt_service.disconnect()
                logger.info("✅ MQTT service desconectado")
            except Exception as e:
                logger.error(f"❌ Error desconectando MQTT: {e}")
                
        logger.info("✅ Servicios cerrados correctamente")


# Crear aplicación FastAPI (9.1)
app = FastAPI(
    title="BomberCat Integrator API",
    description="API completa para gestión de dispositivos BomberCat con WebSocket y MQTT",
    version="2.0",
    lifespan=lifespan,
)

# Middleware CORS (9.1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos
    allow_headers=["*"],  # Permitir todos los headers
)

# Registrar todas las rutas API bajo /api/v1/
register_routes(app)


# Tareas background (9.5)
async def monitor_device_status():
    """Monitorea el estado del dispositivo cada 1 segundo."""
    while background_tasks_running:
        try:
            # Simular detección de dispositivo
            device_info = {
                "connected": True,
                "port": "/dev/ttyUSB0",
                "chip_type": "ESP32",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "flash_size": "4MB"
            }
            
            await connection_manager.broadcast_device_status(device_info)
            await asyncio.sleep(1.0)  # Cada 1 segundo
            
        except Exception as e:
            logger.error(f"Error en monitor_device_status: {e}")
            await asyncio.sleep(5.0)
            
            
async def relay_metrics_publisher():
    """Publica métricas del relay cada 100ms."""
    while background_tasks_running:
        try:
            # Simular latencia del relay
            import random
            latency_ms = random.uniform(10.0, 50.0)
            
            # Broadcast latencia
            await connection_manager.broadcast_latency(latency_ms)
            
            # Métricas del sistema
            metrics = {
                "cpu_usage": random.uniform(10.0, 80.0),
                "memory_usage": random.uniform(20.0, 70.0),
                "network_rx": random.uniform(100.0, 1000.0),
                "network_tx": random.uniform(50.0, 500.0),
                "relay_packets": random.randint(100, 1000),
                "relay_errors": random.randint(0, 5)
            }
            
            await connection_manager.broadcast_metrics(metrics)
            
            # Publicar a MQTT si está disponible
            if mqtt_service:
                try:
                    telemetry_data = {
                        "latency_ms": latency_ms,
                        "timestamp": time.time(),
                        **metrics
                    }
                    await mqtt_service.publish_telemetry(telemetry_data)
                except Exception as e:
                    logger.debug(f"Error publicando a MQTT: {e}")
                    
            await asyncio.sleep(0.1)  # Cada 100ms
            
        except Exception as e:
            logger.error(f"Error en relay_metrics_publisher: {e}")
            await asyncio.sleep(1.0)




# Los endpoints REST ahora están organizados en /api/v1/ via register_routes()
# Solo mantenemos aquí los endpoints especiales que no van bajo /api/v1/


# WebSocket handler (9.4)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Manejador principal de WebSocket con eco de comandos y broadcast."""
    await connection_manager.connect(websocket)
    
    try:
        # Enviar estado inicial
        initial_status = {
            "type": "connection_established",
            "message": "Conectado al WebSocket de BomberCat",
            "timestamp": time.time()
        }
        await connection_manager.send_personal_message(json.dumps(initial_status), websocket)
        
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_text()
            
            try:
                # Parsear comando
                command = json.loads(data)
                
                # Validar estructura del comando
                if not isinstance(command, dict) or "type" not in command:
                    await connection_manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Formato de comando inválido",
                            "timestamp": time.time()
                        }),
                        websocket
                    )
                    continue
                
                # Eco del comando recibido
                echo_response = {
                    "type": "command_echo",
                    "original_command": command,
                    "timestamp": time.time()
                }
                await connection_manager.send_personal_message(json.dumps(echo_response), websocket)
                
                # Procesar comandos específicos
                command_type = command.get("type")
                
                if command_type == "ping":
                    pong_response = {
                        "type": "pong",
                        "timestamp": time.time()
                    }
                    await connection_manager.send_personal_message(json.dumps(pong_response), websocket)
                    
                elif command_type == "get_status":
                    # Enviar estado actual
                    status_response = await get_status()
                    status_data = {
                        "type": "status_response",
                        "data": status_response.body.decode() if hasattr(status_response, 'body') else {},
                        "timestamp": time.time()
                    }
                    await connection_manager.send_personal_message(json.dumps(status_data), websocket)
                    
                elif command_type == "subscribe":
                    # Confirmar suscripción
                    subscribe_response = {
                        "type": "subscribed",
                        "channels": command.get("channels", ["all"]),
                        "timestamp": time.time()
                    }
                    await connection_manager.send_personal_message(json.dumps(subscribe_response), websocket)
                    
                else:
                    # Comando no reconocido
                    unknown_response = {
                        "type": "unknown_command",
                        "message": f"Comando '{command_type}' no reconocido",
                        "timestamp": time.time()
                    }
                    await connection_manager.send_personal_message(json.dumps(unknown_response), websocket)
                    
            except json.JSONDecodeError:
                # Error de parsing JSON
                error_response = {
                    "type": "parse_error",
                    "message": "Error al parsear JSON",
                    "timestamp": time.time()
                }
                await connection_manager.send_personal_message(json.dumps(error_response), websocket)
                
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
    finally:
        connection_manager.disconnect(websocket)


# Los endpoints / y /health están definidos en register_routes()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )