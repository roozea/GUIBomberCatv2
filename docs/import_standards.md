# Estándares de Import - BomberCat Integrator

Este documento define los estándares y reglas para imports en el proyecto BomberCat Integrator.

## 📋 Reglas Generales

### ✅ Permitido

1. **Imports absolutos únicamente**
   ```python
   from modules.bombercat_flash import FlashService
   from api.dependencies import get_flash_service
   from core.entities.device import Device
   ```

2. **Prefijos estándar para módulos locales**
   - `modules.*` - Módulos de funcionalidad específica
   - `api.*` - Componentes de la API REST/WebSocket
   - `core.*` - Entidades y casos de uso del dominio
   - `services.*` - Servicios de aplicación
   - `adapters.*` - Adaptadores e interfaces
   - `infrastructure.*` - Implementaciones de infraestructura
   - `ui.*` - Componentes de interfaz de usuario
   - `tools.*` - Herramientas de desarrollo
   - `config.*` - Configuraciones del proyecto

3. **Imports de librerías externas**
   ```python
   import asyncio
   from fastapi import FastAPI
   from pydantic import BaseModel
   ```

### ❌ Prohibido

1. **Imports relativos**
   ```python
   # ❌ NO hacer esto
   from .flash_service import FlashService
   from ..entities import Device
   from ...core.use_cases import DeviceManagement
   ```

2. **Modificación de sys.path**
   ```python
   # ❌ NO hacer esto
   import sys
   sys.path.append('../modules')
   ```

3. **Imports circulares**
   ```python
   # ❌ Evitar ciclos como:
   # A imports B, B imports C, C imports A
   ```

## 🏗️ Estructura de Imports por Módulo

### Módulos (`modules/*`)

```python
# modules/bombercat_flash/flash_service.py
from modules.bombercat_flash.flash_manager import FlashManager
from modules.bombercat_flash.progress_tracker import ProgressTracker
from core.entities.device import Device
from adapters.interfaces.services import FlashServiceInterface
```

### API (`api/*`)

```python
# api/routers/flash.py
from fastapi import APIRouter, Depends
from api.dependencies import get_flash_service
from core.use_cases.device_flashing import DeviceFlashingUseCase
from services.flash_service import FlashService
```

### Core (`core/*`)

```python
# core/use_cases/device_flashing.py
from core.entities.device import Device, DeviceStatus
from core.entities.firmware import Firmware
from adapters.interfaces.repositories import DeviceRepository
```

### Services (`services/*`)

```python
# services/flash_service.py
from modules.bombercat_flash import FlashService as FlashModule
from core.use_cases.device_flashing import DeviceFlashingUseCase
from adapters.interfaces.services import FlashServiceInterface
```

### UI (`ui/*`)

```python
# ui/components/dashboard_view.py
import flet as ft
from ui.state import StateManager, BomberCatState
from ui.websocket_manager import WSManager
from ui.components.latency_chart import LatencyChart
```

## 📦 Organización de __init__.py

Cada package debe tener un `__init__.py` que exponga las clases/funciones principales:

```python
# modules/bombercat_flash/__init__.py
"""BomberCat Flash Module.

Módulo para flasheo de dispositivos ESP32.
"""

from modules.bombercat_flash.flash_service import FlashService
from modules.bombercat_flash.flash_manager import FlashManager
from modules.bombercat_flash.progress_tracker import ProgressTracker
from modules.bombercat_flash.errors import FlashError, DeviceNotFoundError

__all__ = [
    'FlashService',
    'FlashManager', 
    'ProgressTracker',
    'FlashError',
    'DeviceNotFoundError'
]
```

## 🔄 Evitar Dependencias Circulares

### Estrategias

1. **Usar interfaces/abstracciones**
   ```python
   # En lugar de importar implementación concreta
   from adapters.interfaces.services import FlashServiceInterface
   
   # En lugar de
   from services.flash_service import FlashService
   ```

2. **Dependency Injection**
   ```python
   # api/dependencies.py
   def get_flash_service() -> FlashServiceInterface:
       return FlashService()
   
   # api/routers/flash.py
   def flash_device(service: FlashServiceInterface = Depends(get_flash_service)):
       pass
   ```

3. **Mover interfaces comunes**
   ```python
   # adapters/interfaces/base_service.py
   class BaseService(ABC):
       @abstractmethod
       async def initialize(self) -> None:
           pass
   ```

## 🛠️ Herramientas de Validación

### Import Analyzer

```bash
# Analizar todo el proyecto
python tools/import_analyzer.py --summary

# Generar reporte detallado
python tools/import_analyzer.py --json report.json

# Generar grafo de dependencias
python tools/import_analyzer.py --dot dependencies.dot
```

### Script de Corrección

```bash
# Corregir imports automáticamente
bash scripts/fix_imports.sh
```

## 📝 Ejemplos de Refactoring

### Antes (Import Relativo)

```python
# modules/bombercat_relay/serial_pipeline.py
from .ring_buffer import RingBuffer  # ❌
from .apdu import APDU  # ❌
```

### Después (Import Absoluto)

```python
# modules/bombercat_relay/serial_pipeline.py
from modules.bombercat_relay.ring_buffer import RingBuffer  # ✅
from modules.bombercat_relay.apdu import APDU  # ✅
```

### Antes (Dependencia Circular)

```python
# services/flash_service.py
from api.websocket_manager import ConnectionManager  # ❌ Circular

# api/websocket_manager.py  
from services.flash_service import FlashService  # ❌ Circular
```

### Después (Usando Interface)

```python
# adapters/interfaces/websocket.py
class WebSocketManagerInterface(ABC):
    @abstractmethod
    async def broadcast_flash_progress(self, progress: dict) -> None:
        pass

# services/flash_service.py
from adapters.interfaces.websocket import WebSocketManagerInterface

class FlashService:
    def __init__(self, ws_manager: WebSocketManagerInterface):
        self.ws_manager = ws_manager
```

## 🧪 Testing de Imports

### Test de Imports Válidos

```python
# tests/test_imports.py
def test_no_relative_imports():
    """Verifica que no hay imports relativos."""
    analyzer = ImportAnalyzer(PROJECT_ROOT)
    report = analyzer.analyze_project()
    assert report.relative_imports_count == 0

def test_no_circular_dependencies():
    """Verifica que no hay dependencias circulares."""
    analyzer = ImportAnalyzer(PROJECT_ROOT)
    cycles = analyzer.detect_circular_dependencies()
    assert len(cycles) == 0
```

## 📊 Métricas de Calidad

### Objetivos

- ✅ 0 imports relativos
- ✅ 0 dependencias circulares  
- ✅ 0 modificaciones de sys.path
- ✅ 100% imports absolutos para módulos locales
- ✅ Interfaces bien definidas entre capas

### Monitoreo Continuo

El CI/CD ejecuta automáticamente:

```yaml
# .github/workflows/ci.yml
- name: Check Import Standards
  run: |
    python tools/import_analyzer.py --summary
    if [ $? -ne 0 ]; then
      echo "❌ Import standards violated"
      exit 1
    fi
```

## 🔧 Configuración de IDEs

### VS Code

```json
// .vscode/settings.json
{
  "python.analysis.autoImportCompletions": true,
  "python.analysis.autoSearchPaths": false,
  "python.analysis.extraPaths": ["./modules", "./api", "./core"]
}
```

### PyCharm

1. Mark directories as "Sources Root":
   - `modules/`
   - `api/`
   - `core/`
   - `services/`

2. Configure import optimization to prefer absolute imports

## 📚 Referencias

- [PEP 8 - Style Guide for Python Code](https://pep8.org/)
- [PEP 328 - Imports: Multi-Line and Absolute/Relative](https://www.python.org/dev/peps/pep-0328/)
- [Real Python - Absolute vs Relative Imports](https://realpython.com/absolute-vs-relative-python-imports/)
- [Clean Architecture in Python](https://github.com/cosmic-python/book)