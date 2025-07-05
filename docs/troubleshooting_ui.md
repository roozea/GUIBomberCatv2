# 🔧 Solución de Problemas - BomberCat UI

## 🚨 Problemas Comunes y Soluciones Rápidas

### 1. 🌐 Ruta Generada con Espacios

**Problema:** La URL generada contiene espacios o caracteres especiales que causan errores de navegación.

**Causa:** El nombre de la aplicación en `ft.app()` contiene espacios o caracteres especiales.

**✅ Arreglo Rápido:**
```python
# ❌ INCORRECTO - Genera espacios en URL
ft.app(
    target=dashboard_app,
    name="BomberCat Dashboard",  # Contiene espacio
    port=8550
)

# ✅ CORRECTO - URL limpia
ft.app(
    target=dashboard_app,
    name="dashboard",  # Sin espacios
    port=8550
)
# Resultado: http://127.0.0.1:8550/dashboard
```

**Implementación Actual:**
En nuestro `ui/main.py` línea 305:
```python
ft.app(
    target=dashboard_app,
    name="BomberCat Dashboard",  # ⚠️ Puede causar problemas
    port=8550,
    view=ft.AppView.WEB_BROWSER,
    web_renderer=ft.WebRenderer.HTML,
)
```

**🔧 Solución Recomendada:**
```python
ft.app(
    target=dashboard_app,
    name="bombercat-dashboard",  # URL amigable
    port=8550,
    view=ft.AppView.WEB_BROWSER,
    web_renderer=ft.WebRenderer.HTML,
)
```

### 2. 🔄 dashboard_app() No Retorna

**Problema:** La función `dashboard_app()` no retorna correctamente, causando que la UI no se cargue.

**Causa:** Uso incorrecto de `await` en función target o bloqueo de la función principal.

**✅ Arreglo Rápido:**
```python
# ❌ INCORRECTO - Función async que no maneja correctamente el ciclo
async def dashboard_app(page: ft.Page):
    app = BomberCatApp()
    await app.initialize(page)
    # ❌ No debe tener await aquí que bloquee
    await some_blocking_operation()  # MALO

# ✅ CORRECTO - Función async que inicializa y permite que Flet maneje el ciclo
async def dashboard_app(page: ft.Page):
    app = BomberCatApp()
    await app.initialize(page)
    # ✅ Tareas de fondo se manejan con asyncio.create_task()
    # La función retorna y Flet maneja el ciclo de vida
```

**Implementación Actual:**
Nuestro código en `ui/main.py` línea 217 está correcto:
```python
async def dashboard_app(page: ft.Page):
    app = BomberCatApp()
    await app.initialize(page)
    # ✅ Correcto - no bloquea el retorno
```

### 3. 🔌 Backend WebSocket No Disponible

**Problema:** Error de conexión WebSocket, la UI no puede comunicarse con el backend.

**Causa:** El servidor FastAPI no está ejecutándose o está en puerto incorrecto.

**✅ Arreglo Rápido:**

1. **Verificar que el backend esté corriendo:**
```bash
# Iniciar backend FastAPI
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

2. **Verificar URL de WebSocket en UI:**
En `ui/main.py` línea 60:
```python
# ❌ Puerto incorrecto
self.ws_manager = WSManager("ws://localhost:8000/ws")

# ✅ Puerto correcto (debe coincidir con backend)
self.ws_manager = WSManager("ws://localhost:8000/ws")
```

3. **Verificar estado de servicios:**
```bash
# Verificar que el puerto esté en uso
lsof -i :8000

# Verificar logs del backend
curl http://localhost:8000/health
```

**🔧 Configuración Actual:**
- Backend: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws`
- UI: `http://localhost:8550`

### 4. 🐛 Error JS en Consola

**Problema:** Errores JavaScript en la consola del navegador.

**Causa:** Problemas de conexión WebSocket o llamadas incorrectas a Flet.

**✅ Diagnóstico:**

1. **Abrir DevTools (F12) → Console**

2. **Errores Comunes:**

   **a) "WebSocket connection failed"**
   ```
   WebSocket connection to 'ws://localhost:8000/ws' failed
   ```
   **Solución:** Verificar que el backend esté corriendo (ver punto 3)

   **b) "Cannot read property 'update_async'"**
   ```
   TypeError: Cannot read property 'update_async' of undefined
   ```
   **Solución:** Revisar llamadas a métodos Flet, asegurar que los componentes estén inicializados

   **c) "Failed to fetch"**
   ```
   Failed to fetch dynamically imported module
   ```
   **Solución:** Problema de red o servidor, verificar conectividad

**🔧 Debugging Avanzado:**
```python
# Agregar logging detallado en WSManager
class WSManager:
    async def connect(self):
        try:
            logger.info(f"Intentando conectar a {self.url}")
            # ... código de conexión
        except Exception as e:
            logger.error(f"Error WebSocket: {e}")
            # Mostrar error en UI también
```

### 5. 🎯 Problemas de Renderizado

**Problema:** La UI no se renderiza correctamente o aparece en blanco.

**Causa:** Problemas con el renderer web o configuración de tema.

**✅ Arreglo Rápido:**
```python
# Probar diferentes configuraciones de renderer
ft.app(
    target=dashboard_app,
    name="dashboard",
    port=8550,
    view=ft.AppView.WEB_BROWSER,
    web_renderer=ft.WebRenderer.HTML,  # Probar CANVAS_KIT si hay problemas
)
```

### 6. 🔄 Problemas de Actualización en Tiempo Real

**Problema:** Los datos no se actualizan en tiempo real.

**Causa:** WebSocket desconectado o problemas en el manejo de mensajes.

**✅ Verificación:**
```python
# En dashboard_view.py, verificar que se llame update()
async def _on_state_change(self):
    # ✅ Asegurar que se actualice la UI
    if self.page:
        self.page.update()
```

## 🛠️ Herramientas de Diagnóstico

### Verificar Estado de Servicios
```bash
# Backend API
curl http://localhost:8000/status

# WebSocket (usando wscat)
npm install -g wscat
wscat -c ws://localhost:8000/ws

# UI
curl http://localhost:8550
```

### Logs Útiles
```bash
# Logs del backend
tail -f logs/api.log

# Logs de la UI (en consola donde se ejecuta)
python3 ui/main.py
```

### Verificar Puertos
```bash
# Ver puertos en uso
netstat -tulpn | grep :8000
netstat -tulpn | grep :8550

# En macOS
lsof -i :8000
lsof -i :8550
```

## 🚀 Configuración Óptima

### Archivo main.py Optimizado
```python
def main():
    """Función principal optimizada."""
    try:
        ft.app(
            target=dashboard_app,
            name="dashboard",  # ✅ Sin espacios
            port=8550,
            view=ft.AppView.WEB_BROWSER,
            web_renderer=ft.WebRenderer.HTML,
            assets_dir="assets",  # Para recursos estáticos
        )
    except KeyboardInterrupt:
        logger.info("Aplicación interrumpida por usuario")
    except Exception as e:
        logger.error(f"Error ejecutando aplicación: {e}")
        sys.exit(1)
```

### Variables de Entorno
```bash
# .env
API_HOST=localhost
API_PORT=8000
UI_PORT=8550
WS_URL=ws://localhost:8000/ws
LOG_LEVEL=INFO
```

## 📋 Checklist de Verificación

- [ ] Backend corriendo en puerto 8000
- [ ] UI corriendo en puerto 8550
- [ ] WebSocket URL correcta (ws://localhost:8000/ws)
- [ ] Nombre de app sin espacios
- [ ] DevTools sin errores JS
- [ ] Logs sin errores críticos
- [ ] Conexión WebSocket establecida
- [ ] Datos actualizándose en tiempo real

## 🆘 Contacto de Soporte

Si los problemas persisten:
1. Exportar logs completos
2. Capturar pantalla de errores
3. Documentar pasos para reproducir
4. Verificar versiones de dependencias

---

**💡 Tip:** Mantén siempre el backend corriendo antes de iniciar la UI para evitar errores de conexión.
