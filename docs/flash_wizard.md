# Flash Wizard - Guía de Usuario

## Descripción General

El **Flash Wizard** es un sistema completo para flashear firmware en dispositivos ESP32/ESP8266 con características avanzadas como progreso en tiempo real, manejo robusto de errores, verificación automática y operación asíncrona.

## Características Principales

### ✨ Progreso en Tiempo Real
- Barra de progreso visual con `tqdm`
- Callbacks personalizables para integración en UI
- Seguimiento detallado del proceso de flasheo

### 🛡️ Manejo Robusto de Errores
- Excepciones específicas para cada tipo de error
- Mensajes de error amigables para el usuario
- Mapeo automático de errores de `esptool`

### ✅ Verificación Automática
- Validación de cabecera de firmware (magic bytes)
- Verificación CRC después del flasheo
- Lectura configurable de datos para verificación

### ⚡ Operación Asíncrona
- Soporte completo para `asyncio`
- Thread-safe para múltiples operaciones concurrentes
- Lock automático para evitar conflictos

## Instalación

### Dependencias Requeridas

```bash
pip install esptool tqdm tenacity
```

### Dependencias del Sistema

- Python 3.8+
- Puerto serie disponible
- Drivers USB-Serial instalados

## Uso Básico

### Importación

```python
from modules.bombercat_flash.flasher import ESPFlasher
from modules.bombercat_flash.progress import ProgressPrinter
from modules.bombercat_flash.errors import FlashError
```

### Flasheo Básico

```python
import asyncio
from pathlib import Path

async def flash_firmware():
    flasher = ESPFlasher()
    
    try:
        result = await flasher.flash_device(
            port="/dev/ttyUSB0",
            firmware_path=Path("firmware.bin"),
            progress_callback=ProgressPrinter()
        )
        print(f"Flasheo exitoso: {result}")
    except FlashError as e:
        print(f"Error de flasheo: {e}")

# Ejecutar
asyncio.run(flash_firmware())
```

### Flasheo con Configuración Personalizada

```python
async def flash_with_config():
    flasher = ESPFlasher(
        baud_rate=460800,  # Velocidad alta
        flash_address=0x1000,  # Dirección personalizada
        verify_after_flash=True  # Verificación automática
    )
    
    # Callback personalizado para progreso
    def on_progress(current, total, message):
        percent = (current / total) * 100
        print(f"Progreso: {percent:.1f}% - {message}")
    
    result = await flasher.flash_device(
        port="/dev/ttyUSB0",
        firmware_path=Path("firmware.bin"),
        progress_callback=on_progress
    )
    
    return result
```

## Manejo de Progreso

### ProgressPrinter (CLI)

```python
from modules.bombercat_flash.progress import ProgressPrinter

# Barra de progreso en terminal
progress = ProgressPrinter(
    description="Flasheando firmware",
    unit="bytes"
)

await flasher.flash_device(
    port="/dev/ttyUSB0",
    firmware_path=Path("firmware.bin"),
    progress_callback=progress
)
```

### Callback Personalizado

```python
from modules.bombercat_flash.progress import CallbackProgressDelegate

def my_progress_handler(current, total, message):
    # Integrar con tu UI
    update_progress_bar(current, total)
    update_status_message(message)

progress = CallbackProgressDelegate(my_progress_handler)

await flasher.flash_device(
    port="/dev/ttyUSB0",
    firmware_path=Path("firmware.bin"),
    progress_callback=progress
)
```

### Múltiples Callbacks

```python
from modules.bombercat_flash.progress import ProgressTracker

# Combinar múltiples tipos de progreso
tracker = ProgressTracker()
tracker.add_delegate(ProgressPrinter())  # CLI
tracker.add_delegate(CallbackProgressDelegate(ui_callback))  # UI

await flasher.flash_device(
    port="/dev/ttyUSB0",
    firmware_path=Path("firmware.bin"),
    progress_callback=tracker
)
```

## Manejo de Errores

### Tipos de Errores

```python
from modules.bombercat_flash.errors import (
    PortBusyError,
    SyncError,
    FlashTimeout,
    ChecksumMismatch,
    InvalidFirmwareError,
    DeviceNotFoundError,
    InsufficientSpaceError,
    UnsupportedDeviceError
)

try:
    await flasher.flash_device(port, firmware_path)
except PortBusyError:
    print("Puerto ocupado - cierra otros programas que usen el puerto")
except SyncError:
    print("Error de sincronización - verifica la conexión")
except FlashTimeout:
    print("Timeout - el proceso tardó demasiado")
except ChecksumMismatch:
    print("Error de verificación - el firmware no se escribió correctamente")
except InvalidFirmwareError:
    print("Firmware inválido - verifica el archivo")
except DeviceNotFoundError:
    print("Dispositivo no encontrado - verifica la conexión")
except FlashError as e:
    print(f"Error general: {e}")
```

### Manejo Robusto

```python
async def flash_with_retry():
    flasher = ESPFlasher()
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            result = await flasher.flash_device(
                port="/dev/ttyUSB0",
                firmware_path=Path("firmware.bin")
            )
            return result
        except (SyncError, FlashTimeout) as e:
            if attempt < max_retries - 1:
                print(f"Intento {attempt + 1} falló: {e}. Reintentando...")
                await asyncio.sleep(2)  # Esperar antes de reintentar
            else:
                raise
        except (PortBusyError, DeviceNotFoundError) as e:
            # Errores que no vale la pena reintentar
            raise
```

## Verificación de Firmware

### Verificación Automática

```python
# Verificación automática después del flasheo
flasher = ESPFlasher(verify_after_flash=True)

result = await flasher.flash_device(
    port="/dev/ttyUSB0",
    firmware_path=Path("firmware.bin")
)
# La verificación se ejecuta automáticamente
```

### Verificación Manual

```python
# Solo verificar sin flashear
try:
    is_valid = await flasher.verify_flash(
        port="/dev/ttyUSB0",
        firmware_path=Path("firmware.bin"),
        read_size=4096  # Leer 4KB para verificación
    )
    print(f"Firmware válido: {is_valid}")
except ChecksumMismatch as e:
    print(f"Verificación falló: {e}")
```

### Validación de Cabecera

```python
# Validar solo la cabecera del firmware
with open("firmware.bin", "rb") as f:
    header = f.read(4)
    
if flasher._validate_firmware_header(header):
    print("Cabecera válida")
else:
    print("Cabecera inválida")
```

## Operaciones Concurrentes

### Múltiples Dispositivos

```python
async def flash_multiple_devices():
    flasher = ESPFlasher()
    
    devices = [
        ("/dev/ttyUSB0", "firmware_device1.bin"),
        ("/dev/ttyUSB1", "firmware_device2.bin"),
        ("/dev/ttyUSB2", "firmware_device3.bin")
    ]
    
    tasks = []
    for port, firmware in devices:
        task = flasher.flash_device(
            port=port,
            firmware_path=Path(firmware),
            progress_callback=ProgressPrinter(description=f"Device {port}")
        )
        tasks.append(task)
    
    # Ejecutar en paralelo
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        port, firmware = devices[i]
        if isinstance(result, Exception):
            print(f"Error en {port}: {result}")
        else:
            print(f"Éxito en {port}: {result}")

asyncio.run(flash_multiple_devices())
```

## Configuración Avanzada

### Parámetros del Flasher

```python
flasher = ESPFlasher(
    baud_rate=460800,           # Velocidad de comunicación
    flash_address=0x1000,       # Dirección de inicio
    verify_after_flash=True,    # Verificación automática
    max_retries=3,              # Reintentos automáticos
    timeout=120                 # Timeout en segundos
)
```

### Configuración de Progreso

```python
# Progreso silencioso para operaciones en background
from modules.bombercat_flash.progress import SilentProgressDelegate

silent_progress = SilentProgressDelegate()

# Progreso con callback personalizado
def custom_callback(current, total, message):
    # Tu lógica personalizada
    pass

custom_progress = CallbackProgressDelegate(custom_callback)
```

## Mejores Prácticas

### 1. Manejo de Recursos

```python
# Usar context manager para cleanup automático
async def safe_flash():
    flasher = ESPFlasher()
    try:
        result = await flasher.flash_device(port, firmware_path)
        return result
    finally:
        # Cleanup automático en ESPFlasher
        pass
```

### 2. Validación Previa

```python
async def validated_flash(port, firmware_path):
    flasher = ESPFlasher()
    
    # Validar archivo antes de flashear
    if not firmware_path.exists():
        raise FileNotFoundError(f"Firmware no encontrado: {firmware_path}")
    
    # Validar cabecera
    with open(firmware_path, "rb") as f:
        header = f.read(4)
    
    if not flasher._validate_firmware_header(header):
        raise InvalidFirmwareError("Cabecera de firmware inválida")
    
    # Proceder con el flasheo
    return await flasher.flash_device(port, firmware_path)
```

### 3. Logging

```python
import logging

# Configurar logging para debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def flash_with_logging(port, firmware_path):
    logger.info(f"Iniciando flasheo en {port}")
    
    try:
        flasher = ESPFlasher()
        result = await flasher.flash_device(port, firmware_path)
        logger.info(f"Flasheo exitoso: {result}")
        return result
    except FlashError as e:
        logger.error(f"Error de flasheo: {e}")
        raise
```

## Troubleshooting

### Problemas Comunes

#### Puerto Ocupado
```bash
# Verificar qué proceso usa el puerto
lsof /dev/ttyUSB0

# Matar proceso si es necesario
sudo kill -9 <PID>
```

#### Permisos de Puerto
```bash
# Agregar usuario al grupo dialout
sudo usermod -a -G dialout $USER

# O cambiar permisos temporalmente
sudo chmod 666 /dev/ttyUSB0
```

#### Velocidad de Baudios
```python
# Probar diferentes velocidades si hay problemas
for baud in [115200, 230400, 460800, 921600]:
    try:
        flasher = ESPFlasher(baud_rate=baud)
        result = await flasher.flash_device(port, firmware_path)
        print(f"Éxito con {baud} baudios")
        break
    except FlashError:
        continue
```

### Debugging

```python
# Habilitar debug en esptool
import os
os.environ['ESPTOOL_DEBUG'] = '1'

# Usar progreso detallado
class DebugProgress:
    def on_start(self, total_size, message):
        print(f"DEBUG: Iniciando - {total_size} bytes - {message}")
    
    def on_chunk(self, current, total, message):
        print(f"DEBUG: {current}/{total} - {message}")
    
    def on_end(self, success, message):
        print(f"DEBUG: Finalizado - {success} - {message}")

await flasher.flash_device(
    port, firmware_path,
    progress_callback=DebugProgress()
)
```

## Rendimiento

### Optimización de Velocidad

- **Baudios altos**: Usar 460800 o 921600 para dispositivos compatibles
- **Verificación selectiva**: Ajustar `read_size` en verificación según necesidades
- **Paralelización**: Flashear múltiples dispositivos en paralelo

### Métricas de Rendimiento

- **Objetivo**: Firmware de 2MB en ≤ 120 segundos a 460k baudios
- **Verificación**: Lectura de 4KB en < 5 segundos
- **Overhead**: < 10% del tiempo total en operaciones auxiliares

## API Reference

Ver documentación detallada de la API en:
- `modules/bombercat_flash/flasher.py` - Clase principal ESPFlasher
- `modules/bombercat_flash/progress.py` - Sistema de progreso
- `modules/bombercat_flash/errors.py` - Excepciones específicas

## Contribuir

Para contribuir al Flash Wizard:

1. Ejecutar tests: `pytest tests/flasher/`
2. Verificar cobertura: `pytest --cov=modules.bombercat_flash`
3. Seguir estilo de código: `black` y `flake8`
4. Documentar cambios en este archivo

## Licencia

Ver archivo LICENSE en el directorio raíz del proyecto.