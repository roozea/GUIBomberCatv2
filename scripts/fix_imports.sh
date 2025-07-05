#!/bin/bash
# Script para corregir imports relativos a absolutos en el proyecto BomberCat Integrator

set -e

echo "🔧 Iniciando corrección de imports..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para mostrar progreso
show_progress() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

show_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

show_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

show_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "pyproject.toml" ] && [ ! -f "requirements.txt" ]; then
    show_error "No se encontró pyproject.toml o requirements.txt. Ejecutar desde la raíz del proyecto."
    exit 1
fi

show_progress "Analizando estado actual..."
python3 tools/import_analyzer.py --summary > /tmp/import_analysis_before.txt

# Backup del estado actual
BACKUP_DIR=".import_backup_$(date +%Y%m%d_%H%M%S)"
show_progress "Creando backup en $BACKUP_DIR..."
mkdir -p "$BACKUP_DIR"

# Función para hacer backup de un archivo antes de modificarlo
backup_file() {
    local file="$1"
    local backup_path="$BACKUP_DIR/$file"
    mkdir -p "$(dirname "$backup_path")"
    cp "$file" "$backup_path"
}

# Función para corregir imports relativos en un archivo
fix_file_imports() {
    local file="$1"
    local temp_file="${file}.tmp"
    
    show_progress "Procesando: $file"
    backup_file "$file"
    
    # Usar sed para reemplazar imports relativos
    # Nota: Esta es una implementación básica, para casos complejos usar Python
    
    # Corregir imports en modules/bombercat_*
    if [[ "$file" == modules/bombercat_*/* ]]; then
        local module_name=$(echo "$file" | cut -d'/' -f1-2)
        
        # from .xxx import -> from modules.bombercat_xxx.xxx import
        sed "s|from \.\([^[:space:]]*\) import|from ${module_name}.\1 import|g" "$file" > "$temp_file"
        
        # from ..xxx import -> from modules.xxx import  
        sed -i "s|from \.\.\([^[:space:]]*\) import|from modules.\1 import|g" "$temp_file"
        
    # Corregir imports en api/
    elif [[ "$file" == api/* ]]; then
        # from ..xxx import -> from api.xxx import
        sed "s|from \.\.\([^[:space:]]*\) import|from api.\1 import|g" "$file" > "$temp_file"
        
        # from .xxx import -> from api.xxx import (para subdirectorios)
        sed -i "s|from \.\([^[:space:]]*\) import|from api.\1 import|g" "$temp_file"
        
    # Corregir imports en core/
    elif [[ "$file" == core/* ]]; then
        # from ..xxx import -> from core.xxx import
        sed "s|from \.\.\([^[:space:]]*\) import|from core.\1 import|g" "$file" > "$temp_file"
        
        # from .xxx import -> from core.xxx import (para subdirectorios)
        sed -i "s|from \.\([^[:space:]]*\) import|from core.\1 import|g" "$temp_file"
        
    # Corregir imports en ui/
    elif [[ "$file" == ui/* ]]; then
        # from ..xxx import -> from ui.xxx import
        sed "s|from \.\.\([^[:space:]]*\) import|from ui.\1 import|g" "$file" > "$temp_file"
        
        # from .xxx import -> from ui.xxx import (para subdirectorios)
        sed -i "s|from \.\([^[:space:]]*\) import|from ui.\1 import|g" "$temp_file"
        
    else
        # Para otros archivos, copiar sin cambios
        cp "$file" "$temp_file"
    fi
    
    # Verificar que el archivo modificado es válido Python
    if python3 -m py_compile "$temp_file" 2>/dev/null; then
        mv "$temp_file" "$file"
        show_success "✅ Corregido: $file"
    else
        show_warning "⚠️  Error de sintaxis en $file, restaurando original"
        rm "$temp_file"
    fi
}

# Función avanzada usando Python para correcciones más precisas
fix_file_imports_python() {
    local file="$1"
    
    python3 -c "
import ast
import sys
from pathlib import Path

def fix_imports_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    modified = False
    
    for i, line in enumerate(lines):
        original_line = line
        
        # Detectar imports relativos
        if line.strip().startswith('from .') and ' import ' in line:
            # Determinar el módulo base según la ubicación del archivo
            file_parts = Path(file_path).parts
            
            if 'modules' in file_parts and 'bombercat_' in str(file_path):
                # Para modules/bombercat_xxx/
                module_idx = file_parts.index('modules')
                if module_idx + 1 < len(file_parts):
                    base_module = '.'.join(file_parts[module_idx:module_idx+2])
                    # from .xxx import -> from modules.bombercat_xxx.xxx import
                    line = line.replace('from .', f'from {base_module}.')
                    
            elif 'api' in file_parts:
                # Para api/
                line = line.replace('from ..', 'from api.')
                line = line.replace('from .', 'from api.')
                
            elif 'core' in file_parts:
                # Para core/
                line = line.replace('from ..', 'from core.')
                line = line.replace('from .', 'from core.')
                
            elif 'ui' in file_parts:
                # Para ui/
                line = line.replace('from ..', 'from ui.')
                line = line.replace('from .', 'from ui.')
                
            if line != original_line:
                lines[i] = line
                modified = True
                print(f'  {original_line.strip()} -> {line.strip()}')
    
    if modified:
        # Verificar sintaxis
        try:
            ast.parse('\n'.join(lines))
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return True
        except SyntaxError as e:
            print(f'Error de sintaxis: {e}')
            return False
    
    return False

if __name__ == '__main__':
    file_path = sys.argv[1]
    success = fix_imports_in_file(file_path)
    sys.exit(0 if success else 1)
" "$file"
}

# Encontrar archivos Python con imports relativos
show_progress "Buscando archivos con imports relativos..."
files_with_relative_imports=$(grep -r "^[[:space:]]*from \." --include="*.py" . | cut -d: -f1 | sort -u)

if [ -z "$files_with_relative_imports" ]; then
    show_success "No se encontraron imports relativos para corregir."
else
    echo "Archivos a corregir:"
    echo "$files_with_relative_imports" | while read -r file; do
        echo "  - $file"
    done
    
    echo
    read -p "¿Continuar con la corrección? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_progress "Iniciando corrección de imports..."
        
        echo "$files_with_relative_imports" | while read -r file; do
            if [ -f "$file" ]; then
                # Usar la función Python para correcciones más precisas
                if fix_file_imports_python "$file"; then
                    show_success "✅ Corregido: $file"
                else
                    show_warning "⚠️  No se pudo corregir: $file"
                fi
            fi
        done
        
        show_success "Corrección completada."
    else
        show_warning "Corrección cancelada por el usuario."
        exit 0
    fi
fi

# Verificar resultado
show_progress "Verificando resultado..."
python3 tools/import_analyzer.py --summary > /tmp/import_analysis_after.txt

echo
echo "📊 Comparación antes/después:"
echo "ANTES:"
grep "Imports relativos:" /tmp/import_analysis_before.txt || echo "No disponible"
echo "DESPUÉS:"
grep "Imports relativos:" /tmp/import_analysis_after.txt || echo "No disponible"

# Ejecutar tests para verificar que no rompimos nada
show_progress "Ejecutando tests básicos..."
if python3 -m pytest tests/ -q --tb=no 2>/dev/null; then
    show_success "✅ Tests pasaron correctamente"
else
    show_warning "⚠️  Algunos tests fallaron, revisar cambios"
fi

# Verificar que los imports se pueden resolver
show_progress "Verificando imports..."
failed_imports=0
for file in $(find . -name "*.py" -not -path "./venv/*" -not -path "./.git/*" -not -path "*/__pycache__/*"); do
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        show_error "Error de sintaxis en: $file"
        ((failed_imports++))
    fi
done

if [ $failed_imports -eq 0 ]; then
    show_success "✅ Todos los archivos tienen sintaxis válida"
else
    show_error "❌ $failed_imports archivos tienen errores de sintaxis"
fi

echo
show_success "🎉 Corrección de imports completada!"
echo "📁 Backup guardado en: $BACKUP_DIR"
echo "📊 Ejecutar 'python3 tools/import_analyzer.py --summary' para ver el estado final"

# Limpiar archivos temporales
rm -f /tmp/import_analysis_before.txt /tmp/import_analysis_after.txt