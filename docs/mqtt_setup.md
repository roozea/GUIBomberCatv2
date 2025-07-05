# Configuración MQTT para AWS IoT Core

Guía completa para configurar y usar el servicio MQTT con AWS IoT Core.

## Requisitos

### Dependencias de Python

```bash
pip install awscrt awsiot tenacity uuid
```

### Certificados AWS IoT

Necesitas los siguientes archivos de certificados:

1. **Certificado del dispositivo** (`device.pem.crt`)
2. **Clave privada** (`private.pem.key`)
3. **Certificado raíz de Amazon** (`AmazonRootCA1.pem`)

## Configuración en AWS IoT Core

### 1. Crear una "Thing" (Cosa)

1. Ve a la consola de AWS IoT Core
2. Navega a **Manage > Things**
3. Haz clic en **Create things**
4. Selecciona **Create single thing**
5. Asigna un nombre (ej: `bombercat-device-001`)
6. Haz clic en **Next**

### 2. Generar certificados

1. Selecciona **Auto-generate a new certificate**
2. Haz clic en **Next**
3. Descarga los siguientes archivos:
   - Device certificate (`.pem.crt`)
   - Private key file (`.pem.key`)
   - Root CA certificate (`AmazonRootCA1.pem`)
4. **¡Importante!** Activa el certificado antes de continuar

### 3. Crear política IoT

1. Ve a **Secure > Policies**
2. Haz clic en **Create policy**
3. Nombre: `BombercatDevicePolicy`
4. Agrega las siguientes declaraciones:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect"
      ],
      "Resource": "arn:aws:iot:REGION:ACCOUNT:client/bombercat-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iot:Publish"
      ],
      "Resource": [
        "arn:aws:iot:REGION:ACCOUNT:topic/bombercat/telemetry",
        "arn:aws:iot:REGION:ACCOUNT:topic/bombercat/events"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iot:Subscribe",
        "iot:Receive"
      ],
      "Resource": [
        "arn:aws:iot:REGION:ACCOUNT:topicfilter/bombercat/commands/*",
        "arn:aws:iot:REGION:ACCOUNT:topic/bombercat/commands/*"
      ]
    }
  ]
}
```

**Nota:** Reemplaza `REGION` y `ACCOUNT` con tus valores reales.

### 4. Adjuntar política al certificado

1. Ve a **Secure > Certificates**
2. Selecciona tu certificado
3. En **Actions**, selecciona **Attach policy**
4. Selecciona `BombercatDevicePolicy`
5. Haz clic en **Attach**

### 5. Obtener endpoint

1. Ve a **Settings**
2. Copia el **Device data endpoint**
3. Será algo como: `xxxxx-ats.iot.us-east-1.amazonaws.com`

## Configuración del Código

### Opción 1: Variables de entorno

```bash
export AWS_IOT_ENDPOINT="xxxxx-ats.iot.us-east-1.amazonaws.com"
export AWS_IOT_CERT_PATH="/path/to/device.pem.crt"
export AWS_IOT_KEY_PATH="/path/to/private.pem.key"
export AWS_IOT_CA_PATH="/path/to/AmazonRootCA1.pem"
export AWS_IOT_CLIENT_ID="bombercat-device-001"
```

```python
from modules.bombercat_mqtt import AWSIoTService

# Crear servicio desde variables de entorno
service = AWSIoTService.from_env(device_id="bombercat-001")
```

### Opción 2: Configuración directa

```python
from modules.bombercat_mqtt import AWSIoTService, MQTTConfig

config = MQTTConfig(
    endpoint="xxxxx-ats.iot.us-east-1.amazonaws.com",
    cert_path="/path/to/device.pem.crt",
    key_path="/path/to/private.pem.key",
    ca_path="/path/to/AmazonRootCA1.pem",
    client_id="bombercat-device-001",
    device_id="bombercat-001"
)

service = AWSIoTService(config)
```

## Uso Básico

### Iniciar y detener el servicio

```python
import asyncio

async def main():
    # Iniciar servicio
    success = await service.start()
    if not success:
        print("Error iniciando servicio MQTT")
        return
    
    print("Servicio MQTT iniciado")
    
    # Tu código aquí...
    
    # Detener servicio
    await service.stop()
    print("Servicio MQTT detenido")

asyncio.run(main())
```

### Publicar telemetría

```python
# Datos de sensores
telemetry_data = {
    "temperature": 25.5,
    "humidity": 60.0,
    "pressure": 1013.25,
    "location": {
        "lat": -23.5505,
        "lon": -46.6333
    }
}

success = await service.publish_telemetry(telemetry_data)
if success:
    print("Telemetría publicada")
else:
    print("Error publicando telemetría")
```

### Publicar eventos

```python
# Evento de alerta
event_metadata = {
    "sensor_id": "temp_01",
    "threshold": 30.0,
    "current_value": 35.2,
    "severity": "warning",
    "location": "Sala de servidores"
}

success = await service.publish_event("temperature_alert", event_metadata)
if success:
    print("Evento publicado")
else:
    print("Error publicando evento")
```

### Monitorear estado

```python
# Obtener estado del servicio
status = service.status()
print(f"Estado: {status['connection_status']}")
print(f"Conectado: {status['connected']}")
print(f"Intentos de reconexión: {status['reconnect_attempts']}")
print(f"Última publicación: {status['last_publish_ts']}")

# Verificar conexión
if service.is_connected:
    print("Servicio conectado")
else:
    print(f"Servicio no conectado: {service.connection_status.value}")
```

## Ejemplo Completo

```python
import asyncio
import time
from modules.bombercat_mqtt import AWSIoTService

async def mqtt_example():
    # Crear servicio desde variables de entorno
    service = AWSIoTService.from_env(device_id="bombercat-demo")
    
    try:
        # Iniciar servicio
        print("Iniciando servicio MQTT...")
        success = await service.start()
        
        if not success:
            print("Error iniciando servicio")
            return
        
        print("Servicio iniciado exitosamente")
        
        # Publicar telemetría cada 10 segundos
        for i in range(5):
            telemetry = {
                "iteration": i,
                "timestamp": time.time(),
                "random_value": i * 10.5
            }
            
            success = await service.publish_telemetry(telemetry)
            print(f"Telemetría {i}: {'✓' if success else '✗'}")
            
            # Publicar evento ocasional
            if i % 2 == 0:
                event_meta = {"iteration": i, "type": "periodic"}
                await service.publish_event("demo_event", event_meta)
                print(f"Evento {i}: ✓")
            
            await asyncio.sleep(10)
        
        # Mostrar estado final
        status = service.status()
        print(f"\nEstado final:")
        print(f"  Conectado: {status['connected']}")
        print(f"  Reconexiones: {status['reconnect_attempts']}")
        print(f"  Última publicación: {status['last_publish_ts']}")
        
    except KeyboardInterrupt:
        print("\nInterrumpido por usuario")
    
    finally:
        # Detener servicio
        print("Deteniendo servicio...")
        await service.stop()
        print("Servicio detenido")

if __name__ == "__main__":
    asyncio.run(mqtt_example())
```

## Tópicos MQTT

### Telemetría: `bombercat/telemetry`

Estructura del mensaje:

```json
{
  "timestamp": 1234567890.123,
  "device_id": "bombercat-001",
  "data": {
    "temperature": 25.5,
    "humidity": 60.0,
    "custom_field": "valor"
  }
}
```

### Eventos: `bombercat/events`

Estructura del mensaje:

```json
{
  "timestamp": 1234567890.123,
  "device_id": "bombercat-001",
  "event": "sensor_alert",
  "metadata": {
    "severity": "warning",
    "sensor_id": "temp_01",
    "custom_data": "valor"
  }
}
```

## Características Avanzadas

### Reconexión Automática

El servicio maneja automáticamente:

- **Detección de desconexión**: Callbacks automáticos
- **Back-off exponencial**: 1s, 2s, 4s, 8s, 16s
- **Máximo 5 intentos**: Configurable
- **Jitter aleatorio**: Evita thundering herd

### Keepalive

- **Intervalo**: 25 segundos
- **Evento automático**: `keepalive` en `bombercat/events`
- **Payload**: `{"uptime": timestamp, "status": "alive"}`

### QoS (Quality of Service)

- **Nivel**: QoS 1 (AT_LEAST_ONCE)
- **Garantía**: Al menos una entrega
- **Confirmación**: Espera ACK del broker

## Troubleshooting

### Error: "awscrt y awsiot son requeridos"

```bash
pip install awscrt awsiot
```

### Error: "Variables de entorno faltantes"

Verifica que todas las variables estén configuradas:

```bash
echo $AWS_IOT_ENDPOINT
echo $AWS_IOT_CERT_PATH
echo $AWS_IOT_KEY_PATH
echo $AWS_IOT_CA_PATH
```

### Error de conexión

1. **Verifica el endpoint**: Debe ser el correcto para tu región
2. **Verifica certificados**: Rutas correctas y archivos existentes
3. **Verifica política**: Permisos para `iot:Connect` y `iot:Publish`
4. **Verifica certificado activo**: En la consola AWS IoT

### Problemas de reconexión

1. **Verifica red**: Conectividad a internet
2. **Verifica logs**: Mensajes de error detallados
3. **Verifica límites**: Rate limiting en AWS IoT

### Debugging

Habilita logging detallado:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Crear servicio...
```

## Monitoreo en AWS

### CloudWatch Metrics

1. Ve a **CloudWatch > Metrics**
2. Selecciona **AWS/IoT**
3. Métricas disponibles:
   - `PublishIn.Success`
   - `PublishIn.Failure`
   - `Connect.Success`
   - `Connect.Failure`

### AWS IoT Device Defender

1. Ve a **Defend > Detect**
2. Configura reglas de seguridad
3. Monitorea comportamiento anómalo

### Logs de AWS IoT

1. Ve a **Settings**
2. Habilita **Logging**
3. Nivel: `INFO` o `DEBUG`
4. Revisa logs en CloudWatch

## Mejores Prácticas

### Seguridad

1. **Rotar certificados** regularmente
2. **Usar políticas restrictivas** (principio de menor privilegio)
3. **Monitorear accesos** con CloudTrail
4. **Validar datos** antes de publicar

### Performance

1. **Batch messages** cuando sea posible
2. **Usar compresión** para payloads grandes
3. **Limitar frecuencia** de publicación
4. **Monitorear métricas** de latencia

### Reliability

1. **Implementar circuit breaker** para fallos persistentes
2. **Usar buffer local** para datos críticos
3. **Monitorear estado** de conexión
4. **Implementar fallback** para casos extremos

## Referencias

- [AWS IoT Core Documentation](https://docs.aws.amazon.com/iot/)
- [AWS IoT Device SDK Python v2](https://github.com/aws/aws-iot-device-sdk-python-v2)
- [MQTT Protocol Specification](http://mqtt.org/)
- [AWS IoT Core Limits](https://docs.aws.amazon.com/general/latest/gr/iot-core.html)