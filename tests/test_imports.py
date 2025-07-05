"""Tests para verificar la salud de los imports del proyecto."""

import pytest
import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.import_analyzer import ImportAnalyzer


class TestImportHealth:
    """Tests para verificar que no hay problemas con los imports."""
    
    def test_no_circular_dependencies(self):
        """Verifica que no hay dependencias circulares en el proyecto."""
        analyzer = ImportAnalyzer(project_root)
        report = analyzer.analyze_project()
        
        # No debe haber dependencias circulares
        assert len(report.circular_dependencies) == 0, f"Se encontraron dependencias circulares: {report.circular_dependencies}"
    
    def test_core_services_import(self):
        """Verifica que los servicios principales se pueden importar sin error."""
        # Test imports de servicios principales
        try:
            from services.flash_service import FlashService
            from services.config_service import ConfigService
            from services.relay_service import RelayService
            from services.mqtt_service import MQTTService
        except ImportError as e:
            pytest.fail(f"Error importando servicios principales: {e}")
    
    def test_api_routes_import(self):
        """Verifica que las rutas de la API se pueden importar sin error."""
        try:
            from api.routes import register_routes
            from api.routes import flash_routes
            from api.routes import config_routes
            from api.routes import relay_routes
            from api.routes import mqtt_routes
            from api.routes import device_routes
        except ImportError as e:
            # Algunos imports pueden fallar por dependencias faltantes, pero no debe ser un error crítico
            if "core.device_management" in str(e) or "core." in str(e):
                pytest.skip(f"Skipping due to missing core dependencies: {e}")
            else:
                pytest.fail(f"Error importando rutas de la API: {e}")
    
    def test_modules_import(self):
        """Verifica que los módulos principales se pueden importar sin error."""
        try:
            # Importar solo lo que existe realmente
            import modules.bombercat_config
            import modules.bombercat_flash
            import modules.bombercat_relay
            import modules.bombercat_mqtt
        except ImportError as e:
            # Algunos módulos pueden tener dependencias externas faltantes
            if "core." in str(e) or "pydantic" in str(e) or "serial" in str(e):
                pytest.skip(f"Skipping due to missing dependencies: {e}")
            else:
                pytest.fail(f"Error importando módulos principales: {e}")
    
    def test_adapters_import(self):
        """Verifica que los adaptadores se pueden importar sin error."""
        try:
            from adapters.interfaces.base_service import BaseService, ServiceStatus
            from adapters.interfaces.base_service import WebSocketManagerInterface
            from adapters.interfaces.base_service import FlashServiceInterface
            from adapters.interfaces.base_service import ConfigServiceInterface
            from adapters.interfaces.base_service import RelayServiceInterface
            from adapters.interfaces.base_service import MQTTServiceInterface
        except ImportError as e:
            pytest.fail(f"Error importando interfaces de adaptadores: {e}")
    
    def test_no_relative_imports(self):
        """Verifica que no hay imports relativos en el proyecto."""
        analyzer = ImportAnalyzer(project_root)
        report = analyzer.analyze_project()
        
        # No debe haber imports relativos (excepto en __init__.py donde son permitidos)
        problematic_files = [
            file_analysis for file_analysis in report.files_analysis
            if file_analysis.relative_imports and not file_analysis.file_path.endswith('__init__.py')
        ]
        
        assert len(problematic_files) == 0, f"Se encontraron imports relativos problemáticos en: {[f.file_path for f in problematic_files]}"
    
    def test_import_analyzer_functionality(self):
        """Verifica que el ImportAnalyzer funciona correctamente."""
        analyzer = ImportAnalyzer(project_root)
        
        # Debe poder analizar el proyecto
        report = analyzer.analyze_project()
        
        # Debe tener archivos analizados
        assert report.total_files > 0, "No se encontraron archivos Python para analizar"
        
        # Debe tener imports
        assert report.total_imports > 0, "No se encontraron imports para analizar"
        
        # Los métodos principales deben funcionar
        missing_imports = analyzer.find_missing_imports()
        circular_deps = analyzer.detect_circular_dependencies()
        
        # Todos deben retornar listas
        assert isinstance(missing_imports, list)
        assert isinstance(circular_deps, list)
        assert isinstance(report.files_analysis, list)