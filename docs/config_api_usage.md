# API de Configuración BomberCat

Esta documentación describe cómo usar los endpoints de configuración para dispositivos BomberCat.

## Endpoints Disponibles

### POST /config/

Aplica una nueva configuración al dispositivo BomberCat.

**Parámetros del cuerpo (JSON):**
```json
{
  "mode": "client|host",
  "wifi_ssid": "string (máx. 32 bytes)",
  "wifi_password": "string (8-64 caracteres)",
  "encryption_key": "string (32 caracteres hexadecimales)"
}
```

**Ejemplo de solicitud:**
```bash
curl -X POST "http://localhost:8000/config/" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "client",
    "wifi_ssid": "MiRedWiFi",
    "wifi_password": "mipassword123",
    "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
  }'
```

**Respuesta exitosa (200):**
```json
{
  "status": "OK",
  "message": "Configuración aplicada exitosamente",
  "applied_config": {
    "mode": "client",
    "wifi_ssid": "MiRedWiFi",
    "wifi_password": "mipassword123",
    "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
  }
}
```

**Errores posibles:**
- `422`: Error de validación en los datos
- `400`: Error en la transacción o respuesta del dispositivo
- `503`: Error de comunicación serie
- `500`: Error interno del servidor

### GET /config/status

Obtiene el estado actual de la configuración del dispositivo.

**Ejemplo de solicitud:**
```bash
curl -X GET "http://localhost:8000/config/status"
```

**Respuesta exitosa (200):**
```json
{
  "status": "OK",
  "data": {
    "mode": "client",
    "wifi_ssid": "MiRedWiFi",
    "wifi_connected": true,
    "nvs_status": "healthy",
    "last_update": "2024-01-15T10:30:00Z",
    "device_id": "ESP32-S2-001",
    "firmware_version": "1.2.3"
  }
}
```

**Errores posibles:**
- `400`: Error del dispositivo (ej. NVS corrupto)
- `503`: Error de comunicación serie

### POST /config/verify

Verifica la integridad de la configuración actual.

**Ejemplo de solicitud:**
```bash
curl -X POST "http://localhost:8000/config/verify"
```

**Respuesta exitosa (200):**
```json
{
  "status": "OK",
  "verified": true,
  "message": "Configuración verificada exitosamente",
  "verification_data": {
    "config_valid": true,
    "nvs_integrity": "OK",
    "wifi_test": "PASS",
    "encryption_test": "PASS"
  }
}
```

**Respuesta de fallo (400):**
```json
{
  "detail": "Configuration verification failed: Invalid WiFi credentials"
}
```

### POST /config/rollback

Revierte a la última configuración válida guardada.

**Ejemplo de solicitud:**
```bash
curl -X POST "http://localhost:8000/config/rollback"
```

**Respuesta exitosa (200):**
```json
{
  "status": "OK",
  "message": "Rollback completado exitosamente",
  "restored_config": {
    "mode": "client",
    "wifi_ssid": "RedAnterior",
    "wifi_password": "passwordanterior",
    "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
  }
}
```

**Errores posibles:**
- `404`: No hay backup disponible para rollback
- `500`: Error durante el proceso de rollback

### DELETE /config/backup

Limpia backups antiguos de configuración.

**Parámetros de consulta:**
- `keep` (opcional): Número de backups a mantener (por defecto: 10, mínimo: 1)

**Ejemplo de solicitud:**
```bash
curl -X DELETE "http://localhost:8000/config/backup?keep=5"
```

**Respuesta exitosa (200):**
```json
{
  "status": "OK",
  "message": "3 backups antiguos eliminados exitosamente",
  "deleted_count": 3,
  "remaining_count": 5
}
```

## Validaciones de Datos

### Campo `mode`
- **Valores permitidos:** `"client"`, `"host"`
- **Descripción:** Modo de operación del dispositivo BomberCat

### Campo `wifi_ssid`
- **Longitud:** Máximo 32 bytes UTF-8
- **Restricciones:** No puede contener caracteres de control
- **Descripción:** Nombre de la red WiFi

### Campo `wifi_password`
- **Longitud:** 8-64 caracteres
- **Restricciones:** No puede contener caracteres de control
- **Descripción:** Contraseña de la red WiFi

### Campo `encryption_key`
- **Formato:** Exactamente 32 caracteres hexadecimales (0-9, A-F, a-f)
- **Ejemplo:** `"0123456789ABCDEF0123456789ABCDEF"`
- **Descripción:** Clave de encriptación para comunicaciones seguras

## Manejo de Errores

### Códigos de Estado HTTP

- **200 OK:** Operación exitosa
- **400 Bad Request:** Error en los datos o respuesta del dispositivo
- **404 Not Found:** Recurso no encontrado (ej. no hay backup)
- **422 Unprocessable Entity:** Error de validación en los datos de entrada
- **503 Service Unavailable:** Error de comunicación con el dispositivo
- **500 Internal Server Error:** Error interno del servidor

### Formato de Errores

Todos los errores siguen el formato estándar de FastAPI:

```json
{
  "detail": "Descripción del error"
}
```

Para errores de validación (422), el formato incluye detalles específicos:

```json
{
  "detail": [
    {
      "loc": ["wifi_ssid"],
      "msg": "ensure this value has at most 32 characters",
      "type": "value_error.any_str.max_length"
    }
  ]
}
```

## Mecanismo de Backup y Rollback

### Backup Automático
- Antes de aplicar cualquier configuración nueva, se crea automáticamente un backup
- Los backups se almacenan localmente con timestamp
- Se mantienen los últimos 10 backups por defecto

### Rollback Automático
- Si falla la aplicación de una nueva configuración, se ejecuta rollback automático
- El rollback restaura la última configuración válida conocida
- Se incluyen reintentos automáticos en caso de fallos de comunicación

### Rollback Manual
- Usar el endpoint `POST /config/rollback` para revertir manualmente
- Útil cuando se detectan problemas después de aplicar una configuración

## Reintentos y Robustez

### Comunicación Serie
- Máximo 3 intentos para cada comando
- Backoff exponencial entre reintentos (1s, 2s, 4s)
- Timeout configurable por comando (por defecto 5 segundos)

### Transacciones
- Todas las operaciones de configuración son transaccionales
- Garantía de atomicidad: éxito completo o rollback automático
- Manejo robusto de interrupciones y fallos de comunicación

## Ejemplos de Uso

### Configurar dispositivo como cliente WiFi

```python
import requests

config_data = {
    "mode": "client",
    "wifi_ssid": "MiRedCasa",
    "wifi_password": "mipasswordseguro",
    "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
}

response = requests.post(
    "http://localhost:8000/config/",
    json=config_data
)

if response.status_code == 200:
    print("Configuración aplicada exitosamente")
    print(response.json())
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

### Verificar estado y hacer rollback si es necesario

```python
import requests
import time

# Aplicar nueva configuración
config_response = requests.post(
    "http://localhost:8000/config/",
    json=new_config
)

if config_response.status_code == 200:
    # Esperar un momento para que se aplique
    time.sleep(2)
    
    # Verificar que la configuración funciona
    verify_response = requests.post(
        "http://localhost:8000/config/verify"
    )
    
    if verify_response.status_code != 200:
        print("Verificación falló, haciendo rollback...")
        rollback_response = requests.post(
            "http://localhost:8000/config/rollback"
        )
        print(f"Rollback: {rollback_response.json()}")
    else:
        print("Configuración verificada exitosamente")
else:
    print(f"Error aplicando configuración: {config_response.json()}")
```

### Monitoreo del estado del dispositivo

```python
import requests
import time

def monitor_device_status(interval=30):
    """Monitorea el estado del dispositivo cada 'interval' segundos."""
    while True:
        try:
            response = requests.get(
                "http://localhost:8000/config/status",
                timeout=10
            )
            
            if response.status_code == 200:
                status = response.json()
                print(f"Estado: {status['data']}")
                
                if not status['data'].get('wifi_connected', False):
                    print("⚠️  WiFi desconectado")
                    
            else:
                print(f"Error obteniendo estado: {response.status_code}")
                
        except requests.RequestException as e:
            print(f"Error de conexión: {e}")
            
        time.sleep(interval)

# Ejecutar monitoreo
monitor_device_status()
```

## Consideraciones de Seguridad

### Claves de Encriptación
- Las claves deben ser generadas de forma segura
- Usar generadores criptográficamente seguros
- No reutilizar claves entre dispositivos

### Contraseñas WiFi
- Evitar contraseñas débiles o predecibles
- Considerar rotación periódica de credenciales

### Comunicación
- La comunicación serie es local y no está encriptada
- Asegurar acceso físico restringido al dispositivo
- Considerar autenticación adicional para entornos críticos

## Troubleshooting

### Error 503: Service Unavailable
- Verificar que el dispositivo esté conectado
- Comprobar que el puerto serie esté disponible
- Revisar permisos de acceso al puerto serie

### Error 400: Bad Request con "NVS corrupted"
- El almacenamiento NVS del dispositivo está dañado
- Puede requerir reflash del firmware
- Contactar soporte técnico

### Rollback falla repetidamente
- Verificar integridad de los backups locales
- Comprobar comunicación serie
- Considerar restauración manual del firmware

### Configuración se pierde después de reinicio
- Verificar que el comando SET_CONFIG se ejecutó correctamente
- Comprobar estado del NVS con GET /config/status
- Puede indicar problema de hardware en el ESP32-S2