# NFC Relay Core

Un sistema de relay NFC de alto rendimiento para interceptar y retransmitir comunicaciones APDU entre dispositivos NFC con monitoreo de latencia en tiempo real.

## 🚀 Características

- **Relay Bidireccional**: Intercepta y retransmite APDUs entre cliente y host
- **Monitoreo de Latencia**: Medición de latencia en tiempo real con métricas detalladas
- **Parser APDU Robusto**: Soporte completo para casos APDU 1, 2, 3 y 4
- **Comunicación Serie**: Interfaz optimizada para dispositivos NFC vía puerto serie
- **Métricas Avanzadas**: Estadísticas de throughput, latencia y tasas de error
- **API Asíncrona**: Diseño completamente asíncrono para máximo rendimiento
- **Configuración Flexible**: Parámetros ajustables para diferentes escenarios

## 📋 Requisitos

- Python 3.8+
- Dispositivos NFC compatibles con comunicación serie
- Puertos serie disponibles (USB-to-Serial, UART, etc.)

## 🛠️ Instalación

### Instalación desde el código fuente

```bash
# Clonar el repositorio
git clone <repository-url>
cd BomberCatIntegratorV2_TM

# Instalar dependencias
pip install -e .

# Para desarrollo (incluye herramientas de testing)
pip install -e ".[dev]"
```

### Dependencias principales

- `pyserial`: Comunicación serie
- `numpy`: Cálculos estadísticos
- `rich`: Interfaz de usuario mejorada (para demo)

## 🎯 Uso Rápido

### Demo Interactiva

```bash
python demo_nfc_relay.py
```

Esta demo muestra:
- Configuración del relay
- Métricas en tiempo real
- Simulación de tráfico APDU
- Análisis de rendimiento

### Uso Programático

```python
import asyncio
from modules.bombercat_relay import NFCRelayService, RelayConfig

async def main():
    # Configurar el relay
    config = RelayConfig(
        client_port="/dev/ttyUSB0",
        host_port="/dev/ttyUSB1",
        baud_rate=115200,
        latency_threshold_ms=5.0
    )
    
    # Crear y iniciar servicio
    relay = NFCRelayService(config)
    await relay.start()
    
    try:
        # El relay funciona automáticamente
        await asyncio.sleep(60)  # Ejecutar por 1 minuto
        
        # Obtener estadísticas
        stats = relay.get_stats()
        print(f"APDUs procesados: {stats.total_apdus_processed}")
        print(f"Latencia promedio: {stats.average_latency_ms:.2f}ms")
        
    finally:
        await relay.stop()

asyncio.run(main())
```

## 📊 Monitoreo de Métricas

### Métricas Disponibles

- **Latencia**: Promedio, mínimo, máximo, percentiles (P50, P95, P99)
- **Throughput**: Mensajes por segundo, bytes por segundo
- **Errores**: Tasa de error, tipos de error
- **Uptime**: Tiempo de funcionamiento, disponibilidad

### Ejemplo de Métricas

```python
from modules.bombercat_relay import LatencyMeter, MetricsCollector

# Crear medidor de latencia
meter = LatencyMeter(history_size=1000)

# Medir operación
measurement_id = meter.start_measurement("apdu_001")
# ... realizar operación ...
meter.end_measurement(measurement_id)

# Obtener estadísticas
stats = meter.get_latency_stats()
print(f"Latencia promedio: {stats.mean_ms:.2f}ms")
print(f"P95: {stats.p95_ms:.2f}ms")
```

## 🔧 Configuración

### RelayConfig

```python
config = RelayConfig(
    client_port="/dev/ttyUSB0",      # Puerto del cliente NFC
    host_port="/dev/ttyUSB1",        # Puerto del host NFC
    baud_rate=115200,                # Velocidad de comunicación
    buffer_size=8192,                # Tamaño del buffer
    latency_threshold_ms=5.0,        # Umbral de latencia (ms)
    enable_flow_control=True,        # Control de flujo
    enable_metrics=True,             # Habilitar métricas
    timeout_seconds=1.0              # Timeout de operaciones
)
```

### Parámetros de Latencia

- `history_size`: Número de mediciones a mantener en memoria
- `latency_threshold_ms`: Umbral para alertas de latencia alta
- `enable_async_publishing`: Publicación asíncrona de métricas

## 📡 Protocolo APDU

### Casos Soportados

| Caso | Descripción | Formato |
|------|-------------|----------|
| 1 | Solo comando | `CLA INS P1 P2` |
| 2 | Comando + Le | `CLA INS P1 P2 Le` |
| 3 | Comando + Lc + Data | `CLA INS P1 P2 Lc Data` |
| 4 | Comando + Lc + Data + Le | `CLA INS P1 P2 Lc Data Le` |

### Ejemplo de Parsing

```python
from modules.bombercat_relay import APDU

# Parsear APDU
apdu_bytes = bytes([0x00, 0xA4, 0x04, 0x00, 0x07, 0xA0, 0x00, 0x00, 0x00, 0x04, 0x10, 0x10])
apdu = APDU.parse_apdu(apdu_bytes)

if apdu and apdu.is_valid:
    print(f"Clase: 0x{apdu.cla:02X}")
    print(f"Instrucción: 0x{apdu.ins:02X}")
    print(f"Caso: {apdu.case}")
    print(f"Datos: {apdu.data.hex() if apdu.data else 'N/A'}")
```

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests específicos
pytest tests/relay/test_apdu.py -v
pytest tests/relay/test_latency.py -v

# Tests con benchmarks
pytest tests/relay/test_latency.py --benchmark-only
```

### Cobertura de Tests

- **APDU Parser**: 100% cobertura de casos y edge cases
- **Latency Meter**: Tests de concurrencia y precisión
- **Relay Service**: Tests de integración y manejo de errores
- **Benchmarks**: Medición de rendimiento automatizada

## 🏗️ Arquitectura

### Componentes Principales

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   NFC Client    │◄──►│  Relay Service  │◄──►│    NFC Host     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │ Metrics System  │
                       └─────────────────┘
```

### Flujo de Datos

1. **Interceptación**: El relay captura APDUs del cliente
2. **Parsing**: Análisis y validación del formato APDU
3. **Medición**: Inicio del cronómetro de latencia
4. **Retransmisión**: Envío al host NFC
5. **Respuesta**: Captura de la respuesta del host
6. **Métricas**: Registro de latencia y throughput
7. **Retorno**: Envío de respuesta al cliente

## 📈 Rendimiento

### Benchmarks Típicos

- **Latencia promedio**: < 2ms
- **Throughput**: > 1000 APDUs/segundo
- **Overhead del parser**: < 1μs por APDU
- **Memoria**: < 50MB para 10,000 mediciones

### Optimizaciones

- Parser APDU optimizado con validación mínima
- Buffers circulares para métricas históricas
- Comunicación serie asíncrona
- Pooling de objetos para reducir GC

## 🔍 Troubleshooting

### Problemas Comunes

#### Puerto Serie No Disponible
```bash
# Verificar puertos disponibles
python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

#### Latencia Alta
- Verificar velocidad de baudios
- Revisar control de flujo
- Comprobar interferencias electromagnéticas
- Ajustar tamaño de buffer

#### Errores de Parsing APDU
- Verificar formato de datos
- Comprobar longitudes Lc/Le
- Revisar logs de debug

### Logs de Debug

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Habilitar logs detallados
relay = NFCRelayService(config, debug=True)
```

## 🤝 Contribución

### Desarrollo

```bash
# Configurar entorno de desarrollo
pip install -e ".[dev]"

# Ejecutar tests
pytest

# Verificar estilo de código
flake8 modules/
black modules/

# Type checking
mypy modules/
```

### Estructura del Proyecto

```
modules/bombercat_relay/
├── __init__.py          # API pública
├── apdu.py             # Parser APDU
├── metrics.py          # Sistema de métricas
├── relay.py            # Servicio principal
└── serial_interface.py # Comunicación serie

tests/relay/
├── test_apdu.py        # Tests del parser
├── test_latency.py     # Tests de métricas
└── test_integration.py # Tests de integración
```

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.

## 🔗 Enlaces

- [Documentación de APDU](https://en.wikipedia.org/wiki/Smart_card_application_protocol_data_unit)
- [Especificación ISO 7816](https://www.iso.org/standard/54550.html)
- [PySerial Documentation](https://pyserial.readthedocs.io/)

---

**Desarrollado para aplicaciones de seguridad y análisis de comunicaciones NFC**

## Features

- **Device Management**: Discover, register, and manage IoT devices
- **Firmware Management**: Upload, version, and deploy firmware to devices
- **Configuration Management**: Create, deploy, and manage device configurations
- **Device Flashing**: Flash firmware to ESP32/ESP8266 devices with real-time progress tracking
- **AWS IoT Integration**: Deploy configurations and manage devices through AWS IoT Core
- **REST API**: Complete RESTful API with interactive documentation
- **Real-time Updates**: WebSocket support for live progress monitoring

## Architecture

The project follows Clean Architecture principles with clear separation of concerns:

```
├── core/                   # Business logic and entities
│   ├── entities/          # Domain models
│   └── use_cases/         # Business use cases
├── adapters/              # Interface adapters
│   └── interfaces/        # Abstract interfaces
├── infrastructure/        # External service implementations
├── modules/               # Specialized modules
│   └── bombercat_flash/   # Firmware flashing module
├── api/                   # REST API layer
│   └── routers/          # API endpoints
└── scripts/               # Utility scripts
```

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip or poetry for dependency management

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd BomberCatIntegratorV2_TM
```

2. Install dependencies:
```bash
pip install -e .
```

Or using the requirements file:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (optional):
```bash
cp .env.example .env
# Edit .env with your AWS credentials and other settings
```

### Running the API Server

```bash
# Development mode with auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Or using the installed script
bombercat-integrator
```

The API will be available at:
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Devices
- `GET /api/v1/devices` - List all devices
- `POST /api/v1/devices` - Create a new device
- `GET /api/v1/devices/discover` - Discover connected devices
- `GET /api/v1/devices/{device_id}` - Get device details
- `PUT /api/v1/devices/{device_id}` - Update device
- `DELETE /api/v1/devices/{device_id}` - Delete device

### Firmware
- `GET /api/v1/firmware` - List firmware
- `POST /api/v1/firmware` - Upload firmware
- `GET /api/v1/firmware/{firmware_id}` - Get firmware details
- `PUT /api/v1/firmware/{firmware_id}` - Update firmware
- `DELETE /api/v1/firmware/{firmware_id}` - Delete firmware
- `GET /api/v1/firmware/{firmware_id}/download` - Download firmware file

### Configuration
- `GET /api/v1/configuration` - List configurations
- `POST /api/v1/configuration` - Create configuration
- `GET /api/v1/configuration/{config_id}` - Get configuration
- `PUT /api/v1/configuration/{config_id}` - Update configuration
- `DELETE /api/v1/configuration/{config_id}` - Delete configuration
- `POST /api/v1/configuration/{config_id}/deploy` - Deploy to device

### Flashing
- `POST /api/v1/flashing/flash` - Flash firmware to device
- `POST /api/v1/flashing/flash-latest` - Flash latest compatible firmware
- `GET /api/v1/flashing/jobs` - List flash jobs
- `GET /api/v1/flashing/jobs/{job_id}` - Get flash job status
- `DELETE /api/v1/flashing/jobs/{job_id}` - Cancel flash job
- `POST /api/v1/flashing/erase/{device_id}` - Erase device
- `WebSocket /api/v1/flashing/ws/progress/{job_id}` - Real-time progress

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-west-2
AWS_IOT_ENDPOINT=your-iot-endpoint.amazonaws.com

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true

# Logging
LOG_LEVEL=INFO
```

### Device Types Supported

- ESP32 (all variants)
- ESP8266
- ESP32-S2
- ESP32-S3
- ESP32-C3

### Firmware Types

- Application firmware
- Bootloader
- Partition table
- Custom firmware

## Development

### Setting up Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black .

# Linting
flake8 .

# Type checking
mypy .
```

### Project Structure

- **Core Layer**: Contains business entities and use cases
- **Adapters Layer**: Interfaces for external dependencies
- **Infrastructure Layer**: Concrete implementations (ESPTool, AWS IoT)
- **API Layer**: FastAPI application with routers
- **Modules**: Specialized functionality (flash management)

### Adding New Device Types

1. Implement the `FlashingServiceInterface` in the infrastructure layer
2. Register the new adapter in the dependencies
3. Add device type to the entities

### Adding New Features

1. Define entities in `core/entities/`
2. Create use cases in `core/use_cases/`
3. Add interfaces in `adapters/interfaces/`
4. Implement in `infrastructure/`
5. Create API endpoints in `api/routers/`

## Deployment

### Docker (Coming Soon)

```bash
# Build image
docker build -t bombercat-integrator .

# Run container
docker run -p 8000:8000 bombercat-integrator
```

### Production Considerations

- Use a production WSGI server (Gunicorn)
- Configure proper CORS settings
- Set up SSL/TLS certificates
- Use environment-specific configuration
- Set up monitoring and logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Contact: team@bombercat.com

## Changelog

### v0.1.0
- Initial release
- Basic device, firmware, and configuration management
- ESP32/ESP8266 flashing support
- AWS IoT Core integration
- REST API with documentation
- Real-time progress tracking