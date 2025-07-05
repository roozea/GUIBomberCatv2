"""Project paths configuration for BomberCat Integrator.

Define rutas estándar y configuración de paths del proyecto.
"""

from pathlib import Path
from typing import Dict, List


class ProjectPaths:
    """Configuración centralizada de paths del proyecto."""
    
    def __init__(self, root_path: Path = None):
        """Inicializa las rutas del proyecto.
        
        Args:
            root_path: Ruta raíz del proyecto. Si es None, se detecta automáticamente.
        """
        if root_path is None:
            # Detectar automáticamente la raíz del proyecto
            current = Path(__file__).parent
            while current.parent != current:
                if (current / 'pyproject.toml').exists() or (current / 'requirements.txt').exists():
                    root_path = current
                    break
                current = current.parent
            else:
                # Fallback: usar el directorio padre de config
                root_path = Path(__file__).parent.parent
                
        self.ROOT = root_path.resolve()
        
        # Directorios principales
        self.MODULES = self.ROOT / 'modules'
        self.API = self.ROOT / 'api'
        self.UI = self.ROOT / 'ui'
        self.CORE = self.ROOT / 'core'
        self.SERVICES = self.ROOT / 'services'
        self.ADAPTERS = self.ROOT / 'adapters'
        self.INFRASTRUCTURE = self.ROOT / 'infrastructure'
        self.TESTS = self.ROOT / 'tests'
        self.DOCS = self.ROOT / 'docs'
        self.TOOLS = self.ROOT / 'tools'
        self.CONFIG = self.ROOT / 'config'
        self.SCRIPTS = self.ROOT / 'scripts'
        
        # Archivos de configuración
        self.PYPROJECT_TOML = self.ROOT / 'pyproject.toml'
        self.REQUIREMENTS_TXT = self.ROOT / 'requirements.txt'
        self.ENV_EXAMPLE = self.ROOT / '.env.example'
        self.GITIGNORE = self.ROOT / '.gitignore'
        
        # Directorios de build y cache
        self.VENV = self.ROOT / 'venv'
        self.PYCACHE = self.ROOT / '__pycache__'
        self.BUILD = self.ROOT / 'build'
        self.DIST = self.ROOT / 'dist'
        self.EGG_INFO = self.ROOT / '*.egg-info'
        
    def get_module_paths(self) -> List[Path]:
        """Retorna lista de directorios que contienen módulos Python."""
        return [
            self.MODULES,
            self.API,
            self.UI,
            self.CORE,
            self.SERVICES,
            self.ADAPTERS,
            self.INFRASTRUCTURE,
            self.TESTS,
            self.TOOLS,
            self.CONFIG
        ]
        
    def get_source_paths(self) -> List[Path]:
        """Retorna lista de directorios con código fuente (excluyendo tests)."""
        return [
            self.MODULES,
            self.API,
            self.UI,
            self.CORE,
            self.SERVICES,
            self.ADAPTERS,
            self.INFRASTRUCTURE,
            self.TOOLS,
            self.CONFIG
        ]
        
    def get_excluded_paths(self) -> List[Path]:
        """Retorna lista de directorios a excluir del análisis."""
        return [
            self.VENV,
            self.PYCACHE,
            self.BUILD,
            self.DIST,
            self.ROOT / '.git',
            self.ROOT / '.pytest_cache',
            self.ROOT / '.trae',
            self.ROOT / '.taskmaster',
            self.ROOT / '.benchmarks'
        ]
        
    def is_excluded_path(self, path: Path) -> bool:
        """Verifica si un path debe ser excluido del análisis."""
        path = path.resolve()
        
        # Verificar si está en directorios excluidos
        for excluded in self.get_excluded_paths():
            try:
                path.relative_to(excluded)
                return True
            except ValueError:
                continue
                
        # Verificar patrones específicos
        parts = path.parts
        excluded_patterns = {
            '__pycache__',
            '.git',
            '.pytest_cache',
            'venv',
            'build',
            'dist',
            '.trae',
            '.taskmaster',
            '.benchmarks'
        }
        
        return any(part in excluded_patterns for part in parts)
        
    def to_module_name(self, file_path: Path) -> str:
        """Convierte un path de archivo a nombre de módulo Python.
        
        Args:
            file_path: Path del archivo Python
            
        Returns:
            Nombre del módulo (ej: 'modules.bombercat_flash.api')
        """
        try:
            # Hacer path relativo al proyecto
            rel_path = file_path.relative_to(self.ROOT)
            
            # Remover extensión .py
            if rel_path.suffix == '.py':
                rel_path = rel_path.with_suffix('')
                
            # Convertir path a nombre de módulo
            module_name = str(rel_path).replace('/', '.').replace('\\', '.')
            
            # Remover __init__ al final
            if module_name.endswith('.__init__'):
                module_name = module_name[:-9]
                
            return module_name
            
        except ValueError:
            # El archivo no está dentro del proyecto
            return str(file_path)
            
    def from_module_name(self, module_name: str) -> Path:
        """Convierte un nombre de módulo a path de archivo.
        
        Args:
            module_name: Nombre del módulo (ej: 'modules.bombercat_flash.api')
            
        Returns:
            Path del archivo Python
        """
        # Convertir dots a path separators
        rel_path = Path(module_name.replace('.', '/'))
        
        # Intentar como archivo .py
        file_path = self.ROOT / rel_path.with_suffix('.py')
        if file_path.exists():
            return file_path
            
        # Intentar como package (__init__.py)
        package_path = self.ROOT / rel_path / '__init__.py'
        if package_path.exists():
            return package_path
            
        # Retornar path esperado aunque no exista
        return file_path
        
    def get_import_standards(self) -> Dict[str, str]:
        """Retorna estándares de import para el proyecto."""
        return {
            'modules': 'from modules.{submodule} import {item}',
            'api': 'from api.{submodule} import {item}',
            'core': 'from core.{submodule} import {item}',
            'services': 'from services.{submodule} import {item}',
            'adapters': 'from adapters.{submodule} import {item}',
            'infrastructure': 'from infrastructure.{submodule} import {item}',
            'ui': 'from ui.{submodule} import {item}',
            'tools': 'from tools.{submodule} import {item}',
            'config': 'from config.{submodule} import {item}'
        }
        
    def validate_import(self, import_statement: str) -> bool:
        """Valida si un import sigue los estándares del proyecto.
        
        Args:
            import_statement: Statement de import a validar
            
        Returns:
            True si el import es válido según los estándares
        """
        # Imports absolutos permitidos
        allowed_prefixes = [
            'modules.',
            'api.',
            'core.',
            'services.',
            'adapters.',
            'infrastructure.',
            'ui.',
            'tools.',
            'config.'
        ]
        
        # Verificar si es import relativo (no permitido)
        if import_statement.strip().startswith('from .'):
            return False
            
        # Verificar si usa sys.path.append (no permitido)
        if 'sys.path.append' in import_statement:
            return False
            
        # Verificar si usa prefijos permitidos para módulos locales
        for prefix in allowed_prefixes:
            if prefix in import_statement:
                return True
                
        # Permitir imports de librerías externas
        return True
        
    def __str__(self) -> str:
        """Representación string de las rutas del proyecto."""
        return f"ProjectPaths(root={self.ROOT})"
        
    def __repr__(self) -> str:
        """Representación detallada de las rutas del proyecto."""
        return (
            f"ProjectPaths(\n"
            f"  ROOT={self.ROOT}\n"
            f"  MODULES={self.MODULES}\n"
            f"  API={self.API}\n"
            f"  UI={self.UI}\n"
            f"  CORE={self.CORE}\n"
            f"  SERVICES={self.SERVICES}\n"
            f")"
        )


# Instancia global para uso en todo el proyecto
PROJECT_PATHS = ProjectPaths()


# Funciones de conveniencia
def get_project_root() -> Path:
    """Retorna la ruta raíz del proyecto."""
    return PROJECT_PATHS.ROOT


def to_module_name(file_path: Path) -> str:
    """Convierte un path de archivo a nombre de módulo."""
    return PROJECT_PATHS.to_module_name(file_path)


def from_module_name(module_name: str) -> Path:
    """Convierte un nombre de módulo a path de archivo."""
    return PROJECT_PATHS.from_module_name(module_name)


def validate_import(import_statement: str) -> bool:
    """Valida si un import sigue los estándares del proyecto."""
    return PROJECT_PATHS.validate_import(import_statement)