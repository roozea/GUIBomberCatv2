# Dashboard Flet - Guía de Uso

Este documento describe cómo usar el dashboard Flet de BomberCat Integrator para monitorear y controlar el sistema en tiempo real.

## Características

- **UI Responsive**: Adaptable a móvil, tablet y desktop
- **Tiempo Real**: Conexión WebSocket para actualizaciones instantáneas
- **Baja Latencia**: Actualizaciones < 100ms, buffer de 100 puntos
- **Controles**: Flash Device, Start/Stop Relay
- **Arquitectura Desacoplada**: State manager + componentes independientes

## Instalación

Las dependencias ya están incluidas en `pyproject.toml`:

```toml
[tool.poetry.dependencies]
flet = "^0.21.0"
websockets = ">=12.0"
pydantic = "^2.0.0"
rich = "^13.0.0"
```

Instalar dependencias:

```bash
poetry install
```

## Inicio Rápido

### ⚠️ ORDEN CORRECTO DE ARRANQUE: Backend → UI

**CRÍTICO**: Siempre inicia el backend FastAPI ANTES del dashboard para evitar el spinner infinito y errores de conexión WebSocket.

### 1. Arrancar el Backend (OBLIGATORIO PRIMERO)

```bash
# Terminal 1: Arrancar backend FastAPI
cd /ruta/al/proyecto
python3 -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Espera a ver estos mensajes antes de continuar:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Application startup complete.
```

### 2. Arrancar el Dashboard (SEGUNDO)

```bash
# Terminal 2: Arrancar dashboard (SOLO después del backend)
cd /ruta/al/proyecto
python3 ui/main.py
```

**Indicadores de éxito:**
- ✅ Mensaje "UI loaded - Dashboard cargado correctamente"
- ✅ Sin banner de "Backend offline"
- ✅ Dashboard accesible en `http://localhost:8550/bombercat-dashboard/`

### 3. Conexión WebSocket y Manejo de Errores

El dashboard implementa las siguientes mejoras:

**Timeout de Conexión (1 segundo):**
- Si el backend no responde en 1s, muestra banner "Backend offline"
- Permite reintentar conexión sin reiniciar la aplicación

**Indicadores Visuales:**
- 🔄 Loading spinner durante inicialización
- ✅ Banner verde "UI loaded" cuando carga exitosamente
- ⚠️ Banner naranja "Backend offline" si no hay conexión
- 🔄 Botón "Reintentar" para reconectar WebSocket

**Logs de Depuración:**
- Logs detallados con emojis para facilitar debugging
- Mensajes de entrada/salida de funciones críticas
- Estado de conexión WebSocket en tiempo real

## 🛠️ Correcciones Implementadas (Spinner Infinito)

### Problema Resuelto
- **Síntoma**: `/bombercat-dashboard/` devolvía 200 OK pero la página quedaba con el loader infinito
- **Causa**: Función `dashboard_app` no era async y problemas de conexión WebSocket

### Soluciones Implementadas

1. **Cambio a `ft.app_async`**:
   - `dashboard_app` ahora es `async def dashboard_app(page: ft.Page)`
   - `main()` usa `ft.app_async` en lugar de `ft.app`
   - Soporte completo para operaciones asíncronas

2. **Logs de Depuración**:
   - Prints con emojis para tracking de ejecución
   - Logs al entrar/salir de `dashboard_app`
   - Seguimiento de inicialización async

3. **Widget "UI loaded"**:
   - Banner verde de confirmación cuando `page.add` se ejecuta
   - Indicador visual de que la UI se cargó correctamente
   - Botón "OK" para cerrar el banner

4. **Manejo WebSocket con Timeout**:
   - Timeout de 1 segundo para conexión WebSocket
   - Banner "Backend offline" si no conecta
   - Botón "Reintentar" para reconexión
   - Modo offline funcional sin backend

### 4. Interfaz de Usuario

El dashboard incluye:

- **Panel de Control**: Botones para Flash Device, Start/Stop Relay, Scan Devices
- **Gráfico de Latencia**: Visualización en tiempo real de la latencia del sistema
- **Métricas del Sistema**: CPU, memoria, disco, red
- **Logs**: Registro de eventos del sistema
- **Toggle de Tema**: Cambio entre tema oscuro y claro
- **Indicadores de Estado**: Banners para conexión WebSocket y carga de UI

## Arquitectura

### Componentes Principales

```
ui/
├── main.py                    # Punto de entrada Flet
├── websocket_manager.py       # Gestión de conexión WebSocket
├── state.py                   # State manager + Observer pattern
└── components/
    ├── dashboard_view.py      # Layout responsive principal
    ├── latency_chart.py       # Gráfico de latencia en tiempo real
    └── control_panel.py       # Panel de controles
```

### WebSocket Manager (`WSManager`)

```python
from ui.websocket_manager import WSManager

# Crear instancia
ws_manager = WSManager("ws://localhost:8000/ws")

# Conectar
await ws_manager.connect()

# Suscribirse a mensajes
ws_manager.subscribe(callback_function)

# Enviar comando
await ws_manager.send({"cmd": "flash", "data": {}})
```

**Características:**
- Reconexión automática con backoff exponencial
- Máximo 5 reintentos
- Manejo de errores robusto
- Estado de conexión observable

### State Manager (`StateManager`)

```python
from ui.state import StateManager, SystemStatus

# Crear instancia
state_manager = StateManager()

# Agregar listener
state_manager.add_listener(my_callback)

# Actualizar estado
state_manager.update_system_status(SystemStatus.RUNNING)
state_manager.update_relay_status(True)
```

**Patrón Observer:**
- Pub-Sub para notificaciones de cambio de estado
- Listeners reciben eventos < 50ms
- Manejo de excepciones en callbacks

### Responsive Layout

El layout usa `ft.ResponsiveRow` con breakpoints:

- **Mobile**: < 600px (columnas apiladas)
- **Tablet**: 600-1024px (layout híbrido)
- **Desktop**: ≥ 1024px (layout completo)

```python
ft.ResponsiveRow([
    ft.Column(col={"sm": 12, "md": 6, "lg": 4}, controls=[...]),
    ft.Column(col={"sm": 12, "md": 6, "lg": 8}, controls=[...])
])
```

### Gráfico de Latencia

El componente `LatencyChart` mantiene un buffer circular de 100 puntos:

```python
from ui.components.latency_chart import LatencyChart

# Crear gráfico
chart = LatencyChart()

# Agregar punto
chart.add_point(25.5)  # latencia en ms
```

**Optimizaciones:**
- Buffer circular para eficiencia de memoria
- Actualización incremental sin recrear objeto
- Estadísticas automáticas (min, max, promedio)

## Protocolo WebSocket

### Mensajes Entrantes

El dashboard espera mensajes JSON con esta estructura:

```json
{
  "type": "message_type",
  "data": { ... },
  "timestamp": 1234567890.123
}
```

#### Tipos de Mensaje

**Latencia:**
```json
{
  "type": "latency",
  "data": {"value": 25.5},
  "timestamp": 1234567890.123
}
```

**Estado del Relay:**
```json
{
  "type": "relay_status",
  "data": {"running": true}
}
```

**Información del Dispositivo:**
```json
{
  "type": "device_info",
  "data": {
    "name": "ESP32-DevKit",
    "port": "/dev/ttyUSB0",
    "chip_type": "ESP32",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }
}
```

**Progreso de Flash:**
```json
{
  "type": "flash_progress",
  "data": {
    "stage": "Writing",
    "percentage": 75.5,
    "current_step": 3,
    "total_steps": 4,
    "speed_kbps": 256.0
  }
}
```

**Estado del Sistema:**
```json
{
  "type": "system_status",
  "data": {"status": "running"}
}
```

**Logs:**
```json
{
  "type": "log",
  "data": {
    "level": "info",
    "message": "Sistema iniciado",
    "source": "main"
  }
}
```

**Métricas de Rendimiento:**
```json
{
  "type": "metrics",
  "data": {
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "disk_usage": 23.1,
    "network_rx": 1024.0,
    "network_tx": 512.0
  }
}
```

### Mensajes Salientes

El dashboard envía comandos JSON:

**Flash Device:**
```json
{"cmd": "flash", "data": {}}
```

**Start Relay:**
```json
{"cmd": "relay_start", "data": {}}
```

**Stop Relay:**
```json
{"cmd": "relay_stop", "data": {}}
```

**Scan Devices:**
```json
{"cmd": "scan_devices", "data": {}}
```

## Configuración

### Variables de Entorno

```bash
# URL del WebSocket (opcional)
export WEBSOCKET_URL="ws://localhost:8000/ws"

# Puerto del dashboard (opcional)
export DASHBOARD_PORT=8550

# Tema por defecto (opcional)
export DEFAULT_THEME="dark"  # o "light"
```

### Personalización

Puedes personalizar el dashboard modificando:

- **Colores**: Editar `ui/components/dashboard_view.py`
- **Layout**: Modificar breakpoints en `dashboard_view.py`
- **Gráficos**: Ajustar configuración en `latency_chart.py`
- **Controles**: Agregar botones en `control_panel.py`

## Testing

### Ejecutar Tests

```bash
# Tests del WebSocket Manager
pytest tests/ui/test_websocket_manager.py -v

# Tests del State Manager
pytest tests/ui/test_state_binding.py -v

# Todos los tests de UI
pytest tests/ui/ -v
```

### Tests de Latencia

Los tests verifican que:
- Listeners reciben eventos < 50ms
- Procesamiento de 1000 mensajes < 1 segundo
- Buffer circular funciona correctamente

### Mocking WebSocket

Los tests usan mocks de `websockets` para simular:
- Conexiones exitosas/fallidas
- Reconexión automática
- Mensajes entrantes/salientes
- Errores de red

## Troubleshooting

### Problemas Comunes

**Dashboard no se conecta:**
1. Verificar que el servidor WebSocket esté ejecutándose en `localhost:8000`
2. Revisar logs en la consola del dashboard
3. Verificar firewall/proxy

**Latencia alta:**
1. Verificar carga del sistema
2. Revisar conexión de red
3. Comprobar que no hay otros procesos pesados

**UI no responde:**
1. Refrescar la página web
2. Verificar logs de JavaScript en DevTools
3. Reiniciar el dashboard

### Logs de Debug

Para habilitar logs detallados:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Modo de Desarrollo

Para desarrollo, el dashboard incluye datos simulados cuando no hay conexión WebSocket:

```python
# En ui/main.py
if not ws_manager.connected:
    await _simulate_test_data(state_manager)
```

## Rendimiento

### Métricas Objetivo

- **Latencia de UI**: < 100ms
- **Throughput**: 1000+ mensajes/segundo
- **Memoria**: < 100MB
- **CPU**: < 10% en idle

### Optimizaciones

- Buffer circular para datos de latencia
- Actualización incremental de gráficos
- Debouncing de eventos de UI
- Lazy loading de componentes

## Extensiones

### Agregar Nuevos Componentes

1. Crear archivo en `ui/components/`
2. Implementar clase que herede de `ft.UserControl`
3. Suscribirse a `StateManager`
4. Agregar al layout en `dashboard_view.py`

### Agregar Nuevos Comandos

1. Definir comando en `control_panel.py`
2. Agregar botón/control de UI
3. Implementar envío via `WSManager`
4. Actualizar documentación del protocolo

### Agregar Nuevos Tipos de Mensaje

1. Definir estructura en `state.py`
2. Agregar handler en `main.py`
3. Actualizar componentes relevantes
4. Agregar tests correspondientes

## Contribución

Para contribuir al dashboard:

1. Seguir PEP 8 para estilo de código
2. Usar tipado estricto con `mypy`
3. Comentarios en español
4. Tests para nueva funcionalidad
5. Actualizar documentación

### Commits

Usar formato convencional:

```
feat(ui): nueva funcionalidad
fix(ui): corrección de bug
test(ui): agregar tests
docs(ui): actualizar documentación
```
