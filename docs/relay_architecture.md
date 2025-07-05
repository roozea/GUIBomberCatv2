# Arquitectura NFC Relay Core

## Resumen

El **NFC Relay Core** es un servicio bidireccional de alta velocidad que permite reenviar comandos APDU entre un cliente NFC y un host/tarjeta, manteniendo latencias promedio inferiores a 5ms a 921,600 baudios.

## Objetivos de Diseño

- **Latencia Ultra-Baja**: < 5ms promedio para procesamiento APDU
- **Zero-Copy**: Buffers sin copia de memoria para máximo rendimiento
- **Validación APDU**: Parsing y validación completa según ISO 7816
- **Monitoreo en Tiempo Real**: Métricas de latencia y throughput
- **Manejo de Errores**: Control de flujo y recuperación automática
- **Comunicación Serie Optimizada**: Timeouts de 1ms, operaciones no bloqueantes

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                    NFC Relay Service                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   Client Side   │    │   Host Side     │                    │
│  │                 │    │                 │                    │
│  │ ┌─────────────┐ │    │ ┌─────────────┐ │                    │
│  │ │ Serial Port │ │    │ │ Serial Port │ │                    │
│  │ │   (RX/TX)   │ │    │ │   (RX/TX)   │ │                    │
│  │ └─────────────┘ │    │ └─────────────┘ │                    │
│  │        │        │    │        │        │                    │
│  │        ▼        │    │        ▼        │                    │
│  │ ┌─────────────┐ │    │ ┌─────────────┐ │                    │
│  │ │Ring Buffer  │ │    │ │Ring Buffer  │ │                    │
│  │ │(Zero-Copy)  │ │    │ │(Zero-Copy)  │ │                    │
│  │ └─────────────┘ │    │ └─────────────┘ │                    │
│  │        │        │    │        │        │                    │
│  │        ▼        │    │        ▼        │                    │
│  │ ┌─────────────┐ │    │ ┌─────────────┐ │                    │
│  │ │Serial       │ │    │ │Serial       │ │                    │
│  │ │Pipeline     │ │    │ │Pipeline     │ │                    │
│  │ └─────────────┘ │    │ └─────────────┘ │                    │
│  └─────────────────┘    └─────────────────┘                    │
│           │                       │                            │
│           └───────────┬───────────┘                            │
│                       ▼                                        │
│              ┌─────────────────┐                               │
│              │  APDU Parser    │                               │
│              │  & Validator    │                               │
│              └─────────────────┘                               │
│                       │                                        │
│                       ▼                                        │
│              ┌─────────────────┐                               │
│              │ Latency Meter   │                               │
│              │ & Metrics       │                               │
│              └─────────────────┘                               │
│                       │                                        │
│                       ▼                                        │
│              ┌─────────────────┐                               │
│              │ Flow Control    │                               │
│              │ & Error Handler │                               │
│              └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

## Flujo de Datos

### 1. Cliente → Host (Command Flow)

```
Cliente NFC ──[APDU Command]──► Puerto Serie Client
                                       │
                                       ▼
                               Ring Buffer (RX)
                                       │
                                       ▼
                               Serial Pipeline
                                       │
                                       ▼
                               APDU Parser
                                       │
                                       ▼
                               Validación
                                       │
                                       ▼
                               Latency Meter (Start)
                                       │
                                       ▼
                               Ring Buffer (TX)
                                       │
                                       ▼
                               Puerto Serie Host ──► Host/Tarjeta
```

### 2. Host → Cliente (Response Flow)

```
Host/Tarjeta ──[APDU Response]──► Puerto Serie Host
                                        │
                                        ▼
                                Ring Buffer (RX)
                                        │
                                        ▼
                                Serial Pipeline
                                        │
                                        ▼
                                APDU Parser
                                        │
                                        ▼
                                Validación
                                        │
                                        ▼
                                Latency Meter (End)
                                        │
                                        ▼
                                Ring Buffer (TX)
                                        │
                                        ▼
                                Puerto Serie Client ──► Cliente NFC
```

## Componentes Principales

### 1. Ring Buffer (Zero-Copy)

**Archivo**: `modules/bombercat_relay/ring_buffer.py`

- **Propósito**: Buffer circular sin copia de memoria
- **Características**:
  - Usa `memoryview` para operaciones zero-copy
  - Thread-safe con locks mínimos
  - Capacidad configurable
  - Operaciones `write()`, `read()`, `peek()`

```python
buffer = RingBuffer(capacity=4096)
buffer.write(data)  # Sin copia
result = buffer.read(n)  # Sin copia
```

### 2. APDU Parser & Validator

**Archivo**: `modules/bombercat_relay/apdu.py`

- **Propósito**: Parsing y validación de comandos APDU según ISO 7816
- **Características**:
  - Soporte para Cases 1-4 (corto y extendido)
  - Validación de estructura CLA, INS, Lc, Le
  - Cálculo CRC (XOR simple ISO 14443-3)
  - Detección de APDUs completos

```python
if is_complete(buffer):
    apdu = parse_apdu(buffer)
    if apdu and apdu.is_valid:
        # Procesar APDU
```

### 3. Serial Pipeline

**Archivo**: `modules/bombercat_relay/serial_pipeline.py`

- **Propósito**: Comunicación serie optimizada
- **Características**:
  - Operaciones no bloqueantes
  - Timeout de 1ms
  - Pooling de conexiones
  - Reconexión automática en errores

```python
pipeline = SerialPipeline(rx_port, tx_port, buffer)
await pipeline.start()
data = await pipeline.read_async()
await pipeline.write_async(data)
```

### 4. Latency Meter

**Archivo**: `modules/bombercat_relay/metrics.py`

- **Propósito**: Monitoreo de latencia en tiempo real
- **Características**:
  - Resolución de nanosegundos (`time.perf_counter_ns()`)
  - Ventana deslizante de últimas 100 mediciones
  - Estadísticas: promedio, min, max, desviación estándar
  - Publicación vía `asyncio.Queue` para UI

```python
meter = LatencyMeter(window_size=100)
start_time = time.perf_counter_ns()
# ... procesamiento ...
end_time = time.perf_counter_ns()
latency = meter.record_latency(start_time, end_time)
```

### 5. Relay Coordinator

**Archivo**: `modules/bombercat_relay/relay_core.py`

- **Propósito**: Coordinador principal del servicio
- **Características**:
  - Unifica pipelines cliente↔host
  - Gestión de tasks asyncio
  - Control de flujo y errores
  - Métricas centralizadas

```python
relay = NFCRelayService(config)
await relay.start()
metrics = relay.get_metrics()
await relay.stop()
```

## Configuración

### Configuración Serie

```python
config = RelayConfig(
    client_port="/dev/ttyUSB0",
    host_port="/dev/ttyUSB1",
    baudrate=921600,
    timeout_ms=1,
    buffer_size=4096
)
```

### Configuración de Métricas

```python
metrics_config = {
    "latency_window_size": 100,
    "enable_real_time_monitoring": True,
    "metrics_update_interval_ms": 100
}
```

## Optimizaciones de Rendimiento

### 1. Zero-Copy Operations

- **Ring Buffer**: Usa `memoryview` para evitar copias
- **Serial I/O**: Lectura/escritura directa en buffers
- **APDU Processing**: Parsing in-place cuando es posible

### 2. Async/Await Pattern

- **Non-blocking I/O**: Todas las operaciones serie son async
- **Concurrent Processing**: Pipelines cliente y host en paralelo
- **Task Management**: Control fino de corrutinas

### 3. Minimal Locking

- **Lock-free cuando es posible**: Ring buffer con atomic operations
- **Fine-grained locking**: Locks específicos por operación
- **Thread-safe collections**: `deque` para métricas

### 4. Memory Management

- **Pre-allocated buffers**: Evitar allocaciones dinámicas
- **Object pooling**: Reutilización de objetos APDU
- **Garbage collection optimization**: Referencias débiles

## Control de Flujo y Errores

### 1. Detección de Errores

- **APDU malformados**: Validación de estructura
- **Timeouts de comunicación**: Detección de desconexión
- **Buffer overflow**: Manejo de sobrecarga
- **CRC errors**: Validación de integridad

### 2. Recuperación Automática

- **Reconexión serie**: Reabrir puertos en error
- **Retry logic**: Reintento de envío (1 vez)
- **Buffer reset**: Limpieza en errores críticos
- **Graceful degradation**: Modo degradado en fallos

### 3. Flow Control

- **NACK detection**: Detección de acknowledgments negativos
- **Backpressure**: Control de presión hacia atrás
- **Rate limiting**: Limitación de velocidad si necesario
- **Priority queuing**: Priorización de comandos críticos

## Métricas y Monitoreo

### 1. Métricas de Latencia

- **Latencia promedio**: Objetivo < 5ms
- **Latencia mínima/máxima**: Rango de variación
- **Percentiles**: P50, P95, P99
- **Distribución temporal**: Histograma de latencias

### 2. Métricas de Throughput

- **APDUs por segundo**: Velocidad de procesamiento
- **Bytes por segundo**: Ancho de banda utilizado
- **Tasa de errores**: Porcentaje de fallos
- **Tiempo de actividad**: Uptime del servicio

### 3. Métricas de Sistema

- **Uso de CPU**: Carga del procesador
- **Uso de memoria**: Consumo de RAM
- **Buffer utilization**: Ocupación de buffers
- **Thread count**: Número de hilos activos

## Casos de Uso

### 1. Relay NFC Básico

```python
# Configuración simple
config = RelayConfig(
    client_port="/dev/ttyUSB0",
    host_port="/dev/ttyUSB1",
    baudrate=921600
)

# Iniciar servicio
relay = NFCRelayService(config)
await relay.start()

# Monitorear métricas
while True:
    metrics = relay.get_metrics()
    print(f"Latencia: {metrics.latency.mean_ns / 1_000_000:.2f}ms")
    await asyncio.sleep(1)
```

### 2. Relay con Validación Estricta

```python
# Configuración con validación
config = RelayConfig(
    client_port="/dev/ttyUSB0",
    host_port="/dev/ttyUSB1",
    baudrate=921600,
    enable_apdu_validation=True,
    enable_crc_check=True,
    max_retries=1
)

relay = NFCRelayService(config)

# Handler de errores personalizado
async def error_handler(error: RelayError):
    print(f"Error en relay: {error}")
    # Lógica de recuperación

relay.set_error_handler(error_handler)
await relay.start()
```

### 3. Monitoreo en Tiempo Real

```python
# Configurar métricas en tiempo real
config = RelayConfig(
    client_port="/dev/ttyUSB0",
    host_port="/dev/ttyUSB1",
    baudrate=921600,
    enable_real_time_metrics=True
)

relay = NFCRelayService(config)

# Suscribirse a métricas
async def metrics_subscriber():
    async for metrics in relay.metrics_stream():
        if metrics.latency.mean_ns > 5_000_000:  # > 5ms
            print("⚠️  Latencia alta detectada!")
        
        # Actualizar UI en tiempo real
        update_latency_bar(metrics.latency.mean_ns)

# Ejecutar en paralelo
await asyncio.gather(
    relay.start(),
    metrics_subscriber()
)
```

## Testing y Benchmarking

### 1. Tests Unitarios

- **Ring Buffer**: Correctness y zero-copy
- **APDU Parser**: Casos válidos/inválidos
- **Serial Pipeline**: Comunicación mock
- **Latency Meter**: Precisión de mediciones

### 2. Tests de Integración

- **End-to-end**: Cliente → Host → Cliente
- **Error scenarios**: Manejo de fallos
- **Concurrency**: Múltiples APDUs simultáneos
- **Performance**: Latencia bajo carga

### 3. Benchmarks

```bash
# Benchmark principal: 1000 APDUs
pytest tests/relay/test_latency.py::test_1000_apdu_latency_benchmark -v

# Benchmark de componentes
pytest tests/relay/ --benchmark-only

# Benchmark con reporte
pytest tests/relay/ --benchmark-only --benchmark-save=relay_benchmark
```

## Deployment y Configuración

### 1. Dependencias

```bash
pip install pyserial asyncio numpy rich pytest pytest-benchmark
```

### 2. Configuración del Sistema

```bash
# Permisos de puerto serie
sudo usermod -a -G dialout $USER

# Configuración de latencia del kernel
echo 1 | sudo tee /sys/bus/usb-serial/devices/*/latency_timer

# Prioridad de proceso
sudo nice -n -10 python relay_service.py
```

### 3. Monitoreo de Producción

```python
# Logging estructurado
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Métricas para Prometheus
from prometheus_client import Counter, Histogram

apdu_counter = Counter('relay_apdus_total', 'Total APDUs processed')
latency_histogram = Histogram('relay_latency_seconds', 'APDU latency')
```

## Roadmap y Mejoras Futuras

### Versión 2.0

- **Ring Buffer basado en NumPy**: Mayor rendimiento
- **CRC avanzado**: Implementación ISO 14443-3 completa
- **Object pooling**: Reutilización de objetos serie
- **Métricas avanzadas**: Publicación vía Queue para UI
- **Flow control mejorado**: Detección NACK y retry inteligente

### Versión 3.0

- **Multi-relay**: Soporte para múltiples pares cliente-host
- **Load balancing**: Distribución de carga entre relays
- **Encryption**: Cifrado de APDUs en tránsito
- **Web interface**: Dashboard web para monitoreo
- **API REST**: Control remoto del servicio

## Conclusión

El **NFC Relay Core** proporciona una base sólida para aplicaciones de relay NFC de alta velocidad, con énfasis en:

- **Rendimiento**: Latencias < 5ms promedio
- **Confiabilidad**: Manejo robusto de errores
- **Observabilidad**: Métricas detalladas en tiempo real
- **Escalabilidad**: Arquitectura modular y extensible

La implementación modular permite adaptación a diferentes casos de uso manteniendo el rendimiento y la confiabilidad como prioridades principales.