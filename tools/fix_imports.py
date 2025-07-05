#!/usr/bin/env python3
"""Script para corregir imports relativos a absolutos.

Convierte imports relativos a imports absolutos siguiendo los estándares del proyecto.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import argparse
import logging
import shutil
from datetime import datetime


class ImportFixer:
    """Corrige imports relativos en archivos Python."""
    
    def __init__(self, project_root: Path, dry_run: bool = False):
        self.project_root = project_root
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        self.changes_made = 0
        self.files_processed = 0
        
    def fix_file(self, file_path: Path) -> bool:
        """Corrige imports relativos en un archivo específico."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            lines = content.split('\n')
            modified = False
            
            for i, line in enumerate(lines):
                original_line = line
                new_line = self._fix_import_line(line, file_path)
                
                if new_line != original_line:
                    lines[i] = new_line
                    modified = True
                    self.logger.info(f"  {original_line.strip()} -> {new_line.strip()}")
                    
            if modified:
                new_content = '\n'.join(lines)
                
                # Verificar sintaxis
                try:
                    ast.parse(new_content)
                except SyntaxError as e:
                    self.logger.error(f"Error de sintaxis en {file_path}: {e}")
                    return False
                    
                if not self.dry_run:
                    # Hacer backup
                    backup_path = file_path.with_suffix(f'.py.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
                    shutil.copy2(file_path, backup_path)
                    
                    # Escribir archivo corregido
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                        
                self.changes_made += 1
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error procesando {file_path}: {e}")
            return False
            
    def _fix_import_line(self, line: str, file_path: Path) -> str:
        """Corrige una línea de import específica."""
        stripped = line.strip()
        
        # Solo procesar líneas que empiecen con 'from .'
        if not stripped.startswith('from .'):
            return line
            
        # Determinar el módulo base según la ubicación del archivo
        rel_path = file_path.relative_to(self.project_root)
        parts = rel_path.parts
        
        # Determinar el prefijo correcto
        if 'modules' in parts:
            # Para modules/bombercat_xxx/
            module_idx = next(i for i, part in enumerate(parts) if part == 'modules')
            if module_idx + 1 < len(parts) and parts[module_idx + 1].startswith('bombercat_'):
                base_module = f"modules.{parts[module_idx + 1]}"
                
                # from .xxx import -> from modules.bombercat_xxx.xxx import
                if stripped.startswith('from .'):
                    if stripped.startswith('from ..'):  # from ..xxx
                        # from ..xxx import -> from modules.xxx import
                        new_line = line.replace('from ..', 'from modules.')
                    else:  # from .xxx
                        # from .xxx import -> from modules.bombercat_xxx.xxx import
                        new_line = line.replace('from .', f'from {base_module}.')
                    return new_line
                    
        elif 'api' in parts:
            # Para api/
            if stripped.startswith('from ..'):
                return line.replace('from ..', 'from api.')
            elif stripped.startswith('from .'):
                return line.replace('from .', 'from api.')
                
        elif 'core' in parts:
            # Para core/
            if stripped.startswith('from ..'):
                return line.replace('from ..', 'from core.')
            elif stripped.startswith('from .'):
                return line.replace('from .', 'from core.')
                
        elif 'ui' in parts:
            # Para ui/
            if stripped.startswith('from ..'):
                return line.replace('from ..', 'from ui.')
            elif stripped.startswith('from .'):
                return line.replace('from .', 'from ui.')
                
        elif 'services' in parts:
            # Para services/
            if stripped.startswith('from ..'):
                return line.replace('from ..', 'from services.')
            elif stripped.startswith('from .'):
                return line.replace('from .', 'from services.')
                
        elif 'adapters' in parts:
            # Para adapters/
            if stripped.startswith('from ..'):
                return line.replace('from ..', 'from adapters.')
            elif stripped.startswith('from .'):
                return line.replace('from .', 'from adapters.')
                
        elif 'infrastructure' in parts:
            # Para infrastructure/
            if stripped.startswith('from ..'):
                return line.replace('from ..', 'from infrastructure.')
            elif stripped.startswith('from .'):
                return line.replace('from .', 'from infrastructure.')
                
        return line
        
    def find_files_with_relative_imports(self) -> List[Path]:
        """Encuentra archivos con imports relativos."""
        files = []
        
        for file_path in self.project_root.rglob('*.py'):
            # Filtrar archivos en directorios excluidos
            if any(part.startswith('.') or part in ['venv', '__pycache__', 'build', 'dist'] 
                   for part in file_path.parts):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if 'from .' in content:
                    files.append(file_path)
                    
            except Exception as e:
                self.logger.warning(f"No se pudo leer {file_path}: {e}")
                
        return files
        
    def fix_all_files(self) -> None:
        """Corrige todos los archivos con imports relativos."""
        files = self.find_files_with_relative_imports()
        
        if not files:
            self.logger.info("No se encontraron archivos con imports relativos.")
            return
            
        self.logger.info(f"Encontrados {len(files)} archivos con imports relativos:")
        for file_path in files:
            rel_path = file_path.relative_to(self.project_root)
            self.logger.info(f"  - {rel_path}")
            
        if self.dry_run:
            self.logger.info("\n[DRY RUN] Simulando correcciones...")
        else:
            self.logger.info("\nIniciando correcciones...")
            
        for file_path in files:
            rel_path = file_path.relative_to(self.project_root)
            self.logger.info(f"\nProcesando: {rel_path}")
            
            if self.fix_file(file_path):
                self.logger.info(f"✅ Corregido: {rel_path}")
            else:
                self.logger.info(f"⚠️  Sin cambios: {rel_path}")
                
            self.files_processed += 1
            
        self.logger.info(f"\n📊 Resumen:")
        self.logger.info(f"  Archivos procesados: {self.files_processed}")
        self.logger.info(f"  Archivos modificados: {self.changes_made}")
        

def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description='Corrige imports relativos a absolutos'
    )
    parser.add_argument(
        '--project-root',
        type=Path,
        default=Path.cwd(),
        help='Directorio raíz del proyecto'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular cambios sin modificar archivos'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Modo verbose'
    )
    parser.add_argument(
        '--file',
        type=Path,
        help='Corregir un archivo específico'
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Crear fixer
    fixer = ImportFixer(args.project_root, args.dry_run)
    
    if args.file:
        # Corregir archivo específico
        if not args.file.exists():
            logger.error(f"Archivo no encontrado: {args.file}")
            sys.exit(1)
            
        logger.info(f"Corrigiendo archivo: {args.file}")
        if fixer.fix_file(args.file):
            logger.info("✅ Archivo corregido")
        else:
            logger.info("⚠️  Sin cambios necesarios")
    else:
        # Corregir todos los archivos
        fixer.fix_all_files()
        
    if args.dry_run:
        logger.info("\n[DRY RUN] No se realizaron cambios reales.")
    else:
        logger.info("\n✅ Corrección completada.")
        

if __name__ == '__main__':
    main()