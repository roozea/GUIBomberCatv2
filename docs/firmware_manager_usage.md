# Firmware Manager - Guía de Uso Rápido

El `FirmwareManager` permite descargar y verificar firmware para dispositivos BomberCat desde GitHub de forma asíncrona.

## Instalación de Dependencias

```bash
pip install -r requirements.txt
```

## Uso Básico

### Descargar el Firmware Más Reciente

```python
import asyncio
from pathlib import Path
from modules.bombercat_flash.firmware_manager import FirmwareManager

async def download_latest_firmware():
    manager = FirmwareManager("bombercat/firmware-releases")
    
    try:
        # Descarga automática del firmware más reciente
        firmware_path = await manager.download_firmware()
        print(f"Firmware descargado en: {firmware_path}")
        
    except Exception as e:
        print(f"Error descargando firmware: {e}")

# Ejecutar
asyncio.run(download_latest_firmware())
```

### Descargar a Ubicación Específica

```python
async def download_to_specific_path():
    manager = FirmwareManager()
    target_path = Path("./my_firmware/bombercat_latest.bin")
    
    firmware_path = await manager.download_firmware(target_path=target_path)
    print(f"Firmware guardado en: {firmware_path}")

asyncio.run(download_to_specific_path())
```

### Listar Versiones Disponibles

```python
async def list_versions():
    manager = FirmwareManager()
    
    versions = await manager.list_available_versions()
    print("Versiones disponibles:")
    for version in versions:
        print(f"  - {version}")

asyncio.run(list_versions())
```

### Obtener Información del Último Release

```python
async def get_release_info():
    manager = FirmwareManager()
    
    release = await manager.get_latest_release()
    print(f"Última versión: {release['tag_name']}")
    print(f"Fecha: {release['published_at']}")
    print(f"Notas: {release['body'][:200]}...")

asyncio.run(get_release_info())
```

## Características

### ✅ Descarga Asíncrona
- Descarga no bloqueante con `httpx`
- Soporte HTTP/2 para mejor rendimiento
- Barra de progreso automática en terminales interactivos

### ✅ Verificación de Integridad
- Verificación automática SHA256
- Eliminación automática de archivos corruptos
- Extracción inteligente de checksums desde release notes

### ✅ Manejo de Errores Robusto
- Retry automático con backoff exponencial (3 intentos)
- Manejo específico de rate limits de GitHub API
- Timeouts configurables

### ✅ Filtrado Inteligente de Assets
- Detección automática de firmware ESP32-S2
- Filtrado por extensión `.bin`
- Búsqueda por arquitectura en nombre de archivo

## Configuración Avanzada

### Cliente HTTP Personalizado

```python
from modules.bombercat_flash.http_client import HttpClient

async def custom_http_usage():
    async with HttpClient(timeout=60.0) as client:
        response = await client.get("https://api.github.com/repos/bombercat/firmware-releases/releases/latest")
        data = response.json()
        print(f"Última versión: {data['tag_name']}")

asyncio.run(custom_http_usage())
```

### Manejo de Errores Específicos

```python
from modules.bombercat_flash.firmware_manager import (
    FirmwareManager,
    ChecksumError,
    AssetNotFoundError,
    FirmwareError
)

async def robust_download():
    manager = FirmwareManager()
    
    try:
        firmware_path = await manager.download_firmware()
        print(f"✅ Descarga exitosa: {firmware_path}")
        
    except ChecksumError as e:
        print(f"❌ Error de integridad: {e}")
        
    except AssetNotFoundError as e:
        print(f"❌ Firmware no encontrado: {e}")
        
    except FirmwareError as e:
        print(f"❌ Error general: {e}")

asyncio.run(robust_download())
```

## Rendimiento

- **Velocidad**: Descarga típica de 1-2 MB/s
- **Timeout**: 30s para API calls, 60s para descargas
- **Chunks**: 8KB para streaming eficiente
- **Retry**: 3 intentos con backoff exponencial (1s, 2s, 4s)

## Estructura de Archivos

```
modules/bombercat_flash/
├── firmware_manager.py    # Gestor principal
├── http_client.py         # Cliente HTTP con retry
└── ...

tests/firmware/
├── test_http_retry.py     # Tests del cliente HTTP
├── test_asset_discovery.py # Tests de descubrimiento
└── test_checksum.py       # Tests de verificación
```

## Troubleshooting

### Rate Limit de GitHub
Si encuentras errores 403, el sistema automáticamente espera 60 segundos y reintenta.

### Problemas de Conectividad
El sistema reintenta automáticamente hasta 3 veces con backoff exponencial.

### Checksum Inválido
Si el checksum falla, el archivo se elimina automáticamente. Verifica la integridad del release en GitHub.

### Sin Barra de Progreso
La barra de progreso solo aparece en terminales interactivos. En scripts automatizados se omite automáticamente.