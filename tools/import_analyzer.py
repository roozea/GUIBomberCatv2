#!/usr/bin/env python3
"""Import Analyzer Tool for BomberCat Integrator.

Analiza imports, detecta dependencias circulares y genera reportes.
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import argparse
import logging


@dataclass
class ImportInfo:
    """Información sobre un import."""
    module: str
    from_module: Optional[str] = None
    is_relative: bool = False
    level: int = 0  # Para imports relativos (. = 1, .. = 2, etc.)
    line_number: int = 0
    

@dataclass
class FileAnalysis:
    """Análisis de un archivo Python."""
    file_path: str
    imports: List[ImportInfo]
    missing_imports: List[str]
    relative_imports: List[ImportInfo]
    

@dataclass
class CircularDependency:
    """Dependencia circular detectada."""
    cycle: List[str]
    description: str
    

@dataclass
class AnalysisReport:
    """Reporte completo del análisis."""
    total_files: int
    total_imports: int
    relative_imports_count: int
    missing_imports_count: int
    circular_dependencies: List[CircularDependency]
    files_analysis: List[FileAnalysis]
    import_graph: Dict[str, List[str]]
    

class ImportAnalyzer:
    """Analizador de imports para detectar problemas en el codebase."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.logger = logging.getLogger(__name__)
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.file_imports: Dict[str, List[ImportInfo]] = {}
        
    def analyze_file(self, file_path: Path) -> FileAnalysis:
        """Analiza un archivo Python específico."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content, filename=str(file_path))
            imports = []
            relative_imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_info = ImportInfo(
                            module=alias.name,
                            line_number=node.lineno
                        )
                        imports.append(import_info)
                        
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        import_info = ImportInfo(
                            module=node.module,
                            from_module=node.module,
                            is_relative=node.level > 0,
                            level=node.level,
                            line_number=node.lineno
                        )
                        imports.append(import_info)
                        
                        if node.level > 0:
                            relative_imports.append(import_info)
                            
            # Detectar imports faltantes (simplificado)
            missing_imports = self._detect_missing_imports(imports)
            
            relative_path = str(file_path.relative_to(self.project_root))
            self.file_imports[relative_path] = imports
            
            return FileAnalysis(
                file_path=relative_path,
                imports=imports,
                missing_imports=missing_imports,
                relative_imports=relative_imports
            )
            
        except Exception as e:
            self.logger.error(f"Error analizando {file_path}: {e}")
            return FileAnalysis(
                file_path=str(file_path.relative_to(self.project_root)),
                imports=[],
                missing_imports=[],
                relative_imports=[]
            )
            
    def _detect_missing_imports(self, imports: List[ImportInfo]) -> List[str]:
        """Detecta imports que podrían estar faltando (simplificado)."""
        missing = []
        
        for import_info in imports:
            try:
                # Intentar importar el módulo
                if import_info.from_module:
                    __import__(import_info.from_module)
                else:
                    __import__(import_info.module)
            except ImportError:
                # Solo reportar si no es un módulo local
                if not self._is_local_module(import_info.module):
                    missing.append(import_info.module)
            except Exception:
                # Ignorar otros errores
                pass
                
        return missing
        
    def _is_local_module(self, module_name: str) -> bool:
        """Verifica si un módulo es local al proyecto."""
        # Verificar si existe como archivo en el proyecto
        module_path = self.project_root / module_name.replace('.', '/')
        return (
            (module_path.with_suffix('.py')).exists() or
            (module_path / '__init__.py').exists() or
            module_name.startswith('modules.') or
            module_name.startswith('api.') or
            module_name.startswith('core.') or
            module_name.startswith('services.')
        )
        
    def build_import_graph(self) -> Dict[str, List[str]]:
        """Construye el grafo de dependencias entre módulos."""
        graph = defaultdict(set)
        
        for file_path, imports in self.file_imports.items():
            # Convertir path a nombre de módulo
            module_name = self._path_to_module(file_path)
            
            for import_info in imports:
                if self._is_local_module(import_info.module):
                    graph[module_name].add(import_info.module)
                    
        # Convertir sets a listas para serialización
        return {k: list(v) for k, v in graph.items()}
        
    def _path_to_module(self, file_path: str) -> str:
        """Convierte un path de archivo a nombre de módulo."""
        # Remover extensión .py
        if file_path.endswith('.py'):
            file_path = file_path[:-3]
            
        # Convertir slashes a dots
        module_name = file_path.replace('/', '.').replace('\\', '.')
        
        # Remover __init__ al final
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]
            
        return module_name
        
    def detect_circular_dependencies(self) -> List[CircularDependency]:
        """Detecta dependencias circulares usando DFS."""
        graph = self.build_import_graph()
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Encontramos un ciclo
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(CircularDependency(
                    cycle=cycle,
                    description=f"Circular dependency: {' -> '.join(cycle)}"
                ))
                return
                
            if node in visited:
                return
                
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                dfs(neighbor, path + [node])
                
            rec_stack.remove(node)
            
        for node in graph:
            if node not in visited:
                dfs(node, [])
                
        return cycles
        
    def find_missing_imports(self) -> List[str]:
        """Encuentra todos los imports faltantes en el proyecto."""
        all_missing = set()
        
        for file_analysis in self.file_imports.values():
            for import_info in file_analysis:
                if not self._is_local_module(import_info.module):
                    try:
                        __import__(import_info.module)
                    except ImportError:
                        all_missing.add(import_info.module)
                    except Exception:
                        pass
                        
        return list(all_missing)
        
    def analyze_project(self) -> AnalysisReport:
        """Analiza todo el proyecto."""
        self.logger.info(f"Analizando proyecto en: {self.project_root}")
        
        # Encontrar todos los archivos Python
        python_files = list(self.project_root.rglob('*.py'))
        
        # Filtrar archivos en venv, __pycache__, etc.
        python_files = [
            f for f in python_files 
            if not any(part.startswith('.') or part in ['venv', '__pycache__', 'build', 'dist'] 
                      for part in f.parts)
        ]
        
        self.logger.info(f"Encontrados {len(python_files)} archivos Python")
        
        # Analizar cada archivo
        files_analysis = []
        total_imports = 0
        relative_imports_count = 0
        missing_imports_count = 0
        
        for file_path in python_files:
            analysis = self.analyze_file(file_path)
            files_analysis.append(analysis)
            
            total_imports += len(analysis.imports)
            relative_imports_count += len(analysis.relative_imports)
            missing_imports_count += len(analysis.missing_imports)
            
        # Detectar dependencias circulares
        circular_dependencies = self.detect_circular_dependencies()
        
        # Construir grafo de imports
        import_graph = self.build_import_graph()
        
        return AnalysisReport(
            total_files=len(files_analysis),
            total_imports=total_imports,
            relative_imports_count=relative_imports_count,
            missing_imports_count=missing_imports_count,
            circular_dependencies=circular_dependencies,
            files_analysis=files_analysis,
            import_graph=import_graph
        )
        
    def generate_dot_graph(self, output_path: Path) -> None:
        """Genera un archivo DOT para visualizar el grafo de dependencias."""
        graph = self.build_import_graph()
        
        with open(output_path, 'w') as f:
            f.write('digraph ImportGraph {\n')
            f.write('  rankdir=LR;\n')
            f.write('  node [shape=box];\n\n')
            
            # Escribir nodos
            all_nodes = set()
            for source, targets in graph.items():
                all_nodes.add(source)
                all_nodes.update(targets)
                
            for node in sorted(all_nodes):
                f.write(f'  "{node}";\n')
                
            f.write('\n')
            
            # Escribir edges
            for source, targets in graph.items():
                for target in targets:
                    f.write(f'  "{source}" -> "{target}";\n')
                    
            f.write('}\n')
            
        self.logger.info(f"Grafo DOT generado en: {output_path}")
        

def main():
    """Función principal del CLI."""
    parser = argparse.ArgumentParser(
        description='Analiza imports y detecta problemas en el codebase'
    )
    parser.add_argument(
        '--project-root', 
        type=Path, 
        default=Path.cwd(),
        help='Directorio raíz del proyecto'
    )
    parser.add_argument(
        '--json', 
        type=Path,
        help='Guardar reporte en formato JSON'
    )
    parser.add_argument(
        '--dot', 
        type=Path,
        help='Generar grafo DOT de dependencias'
    )
    parser.add_argument(
        '--summary', 
        action='store_true',
        help='Mostrar solo resumen'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Modo verbose'
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Crear analizador
    analyzer = ImportAnalyzer(args.project_root)
    
    # Analizar proyecto
    report = analyzer.analyze_project()
    
    # Mostrar resumen
    print(f"\n📊 Reporte de Análisis de Imports")
    print(f"{'='*50}")
    print(f"Archivos analizados: {report.total_files}")
    print(f"Total imports: {report.total_imports}")
    print(f"Imports relativos: {report.relative_imports_count}")
    print(f"Imports faltantes: {report.missing_imports_count}")
    print(f"Dependencias circulares: {len(report.circular_dependencies)}")
    
    # Mostrar dependencias circulares
    if report.circular_dependencies:
        print(f"\n🔄 Dependencias Circulares Detectadas:")
        for i, cycle in enumerate(report.circular_dependencies, 1):
            print(f"  {i}. {cycle.description}")
    else:
        print(f"\n✅ No se detectaron dependencias circulares")
        
    # Mostrar detalles si no es summary
    if not args.summary:
        # Mostrar archivos con imports relativos
        relative_files = [f for f in report.files_analysis if f.relative_imports]
        if relative_files:
            print(f"\n📁 Archivos con imports relativos:")
            for file_analysis in relative_files[:10]:  # Mostrar solo los primeros 10
                print(f"  - {file_analysis.file_path} ({len(file_analysis.relative_imports)} imports)")
                
        # Mostrar archivos con imports faltantes
        missing_files = [f for f in report.files_analysis if f.missing_imports]
        if missing_files:
            print(f"\n❌ Archivos con imports faltantes:")
            for file_analysis in missing_files[:10]:  # Mostrar solo los primeros 10
                print(f"  - {file_analysis.file_path}: {', '.join(file_analysis.missing_imports)}")
    
    # Guardar reporte JSON
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"\n💾 Reporte guardado en: {args.json}")
        
    # Generar grafo DOT
    if args.dot:
        analyzer.generate_dot_graph(args.dot)
        print(f"\n🎨 Grafo DOT generado en: {args.dot}")
        print(f"   Para visualizar: dot -Tpng {args.dot} -o graph.png")
        
    # Código de salida
    exit_code = 0
    if report.circular_dependencies:
        exit_code = 1
    elif report.missing_imports_count > 0:
        exit_code = 2
        
    sys.exit(exit_code)
    

if __name__ == '__main__':
    main()