# BomberCat Integrator API - Guía de Uso

## Descripción General

La API de BomberCat Integrator v2.0 proporciona una interfaz completa para la gestión de dispositivos BomberCat, incluyendo:

- **WebSocket en tiempo real** para comunicación bidireccional
- **Endpoints REST** para operaciones CRUD
- **Servicios integrados** (Flash, Config, Relay, MQTT)
- **Tareas background** para monitoreo y métricas
- **Broadcast automático** de eventos en < 100ms

## Configuración y Arranque

### Instalación de Dependencias

```bash
pip install fastapi uvicorn websockets pydantic
```

### Arranque del Servidor

```bash
# Desarrollo con auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### URLs de Acceso

- **API Base**: http://localhost:8000
- **Documentación Swagger**: http://localhost:8000/docs
- **Documentación ReDoc**: http://localhost:8000/redoc
- **WebSocket**: ws://localhost:8000/ws

## Endpoints REST

### 1. Estado del Sistema

```bash
# Obtener estado general
curl -X GET "http://localhost:8000/status" \
  -H "accept: application/json"
```

**Respuesta:**
```json
{
  "status": "running",
  "timestamp": 1704387600.123,
  "services": {
    "flash_service": true,
    "config_service": true,
    "relay_service": true,
    "mqtt_service": true
  },
  "device": {
    "connected": true,
    "port": "/dev/ttyUSB0",
    "chip_type": "ESP32"
  },
  "relay": {
    "running": false,
    "connections": 0
  },
  "mqtt": {
    "connected": true
  },
  "websocket_connections": 2
}
```

### 2. Flash de Firmware

```bash
# Flashear dispositivo
curl -X POST "http://localhost:8000/flash" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_path": "/path/to/firmware.bin",
    "port": "/dev/ttyUSB0"
  }'
```

**Respuesta:**
```json
{
  "status": "started",
  "message": "Flash iniciado",
  "firmware_path": "/path/to/firmware.bin",
  "port": "/dev/ttyUSB0"
}
```

### 3. Configuración del Dispositivo

```bash
# Actualizar configuración
curl -X POST "http://localhost:8000/config" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "config_data": {
      "wifi_ssid": "MiWiFi",
      "wifi_password": "password123",
      "mqtt_broker": "192.168.1.100",
      "relay_enabled": true
    }
  }'
```

**Respuesta:**
```json
{
  "status": "success",
  "message": "Configuración actualizada",
  "result": {
    "success": true,
    "updated_config": {
      "device_name": "BomberCat-001",
      "wifi_ssid": "MiWiFi",
      "wifi_password": "password123",
      "mqtt_broker": "192.168.1.100",
      "relay_enabled": true
    }
  }
}
```

### 4. Control del Relay

#### Iniciar Relay

```bash
curl -X POST "http://localhost:8000/relay/start" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "source_port": 8080,
    "target_host": "192.168.1.200",
    "target_port": 80
  }'
```

#### Detener Relay

```bash
curl -X POST "http://localhost:8000/relay/stop" \
  -H "accept: application/json"
```

### 5. Health Check

```bash
# Verificar salud del servicio
curl -X GET "http://localhost:8000/health"
```

## WebSocket

### Conexión WebSocket

```bash
# Usando wscat (instalar con: npm install -g wscat)
wscat -c ws://localhost:8000/ws
```

### Comandos WebSocket

#### 1. Ping/Pong

```json
// Enviar
{"type": "ping"}

// Recibir
{
  "type": "pong",
  "timestamp": 1704387600.123
}
```

#### 2. Obtener Estado

```json
// Enviar
{"type": "get_status"}

// Recibir
{
  "type": "status_response",
  "data": { /* estado completo del sistema */ },
  "timestamp": 1704387600.123
}
```

#### 3. Suscribirse a Eventos

```json
// Enviar
{
  "type": "subscribe",
  "channels": ["device_status", "flash_progress", "relay_metrics"]
}

// Recibir confirmación
{
  "type": "subscribed",
  "channels": ["device_status", "flash_progress", "relay_metrics"],
  "timestamp": 1704387600.123
}
```

### Eventos Automáticos (Broadcast)

La API envía automáticamente estos eventos a todos los clientes conectados:

#### 1. Estado del Dispositivo (cada 1s)

```json
{
  "type": "device_status",
  "data": {
    "connected": true,
    "port": "/dev/ttyUSB0",
    "chip_type": "ESP32",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "flash_size": "4MB"
  },
  "timestamp": 1704387600.123
}
```

#### 2. Latencia del Relay (cada 100ms)

```json
{
  "type": "latency",
  "data": {
    "latency_ms": 25.4,
    "timestamp": 1704387600.123
  }
}
```

#### 3. Métricas del Sistema (cada 100ms)

```json
{
  "type": "metrics",
  "data": {
    "cpu_usage": 45.2,
    "memory_usage": 62.1,
    "network_rx": 1024.5,
    "network_tx": 512.3,
    "relay_packets": 1500,
    "relay_errors": 2
  },
  "timestamp": 1704387600.123
}
```

#### 4. Progreso de Flash

```json
{
  "type": "flash_progress",
  "data": {
    "progress": 75,
    "message": "Verificando...",
    "timestamp": 1704387600.123
  }
}
```

#### 5. Estado del Relay

```json
{
  "type": "relay_status",
  "data": {
    "status": "running",
    "source_port": 8080,
    "target_host": "192.168.1.200",
    "target_port": 80,
    "timestamp": 1704387600.123
  }
}
```

## Integración con Dashboard Flet

La API está diseñada para integrarse perfectamente con el dashboard Flet:

```python
# En el dashboard Flet
import websocket
import json

class WSManager:
    def __init__(self):
        self.ws_url = "ws://localhost:8000/ws"
        
    async def connect(self):
        self.ws = await websocket.connect(self.ws_url)
        
    async def send_command(self, command):
        await self.ws.send(json.dumps(command))
        
    async def listen(self):
        async for message in self.ws:
            data = json.loads(message)
            # Procesar eventos automáticos
            if data["type"] == "latency":
                self.update_latency_chart(data["data"])
            elif data["type"] == "device_status":
                self.update_device_status(data["data"])
```

## Publicación MQTT

La API publica automáticamente métricas a MQTT:

- **Topic de telemetría**: `bombercat/bombercat_integrator/telemetry`
- **Topic de estado**: `bombercat/bombercat_integrator/device/status`
- **Topic de métricas**: `bombercat/bombercat_integrator/relay/metrics`

## Códigos de Estado HTTP

- **200**: Operación exitosa
- **400**: Solicitud inválida
- **500**: Error interno del servidor
- **503**: Servicio no disponible

## Logs y Debugging

Los logs se muestran en la consola con diferentes niveles:

- **INFO**: Eventos importantes del sistema
- **WARNING**: Advertencias (ej. MQTT no disponible)
- **ERROR**: Errores que requieren atención
- **DEBUG**: Información detallada para debugging

## Ejemplos de Pruebas

### Script de Prueba WebSocket

```bash
#!/bin/bash
# test_websocket.sh

echo "Probando WebSocket..."
echo '{"type": "ping"}' | wscat -c ws://localhost:8000/ws
```

### Script de Prueba REST

```bash
#!/bin/bash
# test_endpoints.sh

echo "Probando endpoints REST..."

# Health check
curl -s http://localhost:8000/health | jq

# Status
curl -s http://localhost:8000/status | jq

# Flash (simulado)
curl -s -X POST http://localhost:8000/flash \
  -H "Content-Type: application/json" \
  -d '{"firmware_path": "/tmp/test.bin", "port": "/dev/ttyUSB0"}' | jq
```

## Troubleshooting

### Puerto en Uso

```bash
# Verificar qué proceso usa el puerto
lsof -i :8000

# Cambiar puerto
uvicorn api.main:app --port 8002
```

### Servicios No Disponibles

Si algún servicio no está disponible, la API continuará funcionando pero mostrará advertencias en los logs.

### Conexión MQTT Fallida

La API funciona sin MQTT, pero las métricas no se publicarán externamente.

---

**Versión**: 2.0  
**Última actualización**: 2024-01-04  
**Soporte**: BomberCat Integrator Team
