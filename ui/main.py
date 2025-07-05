#!/usr/bin/env python3
"""
BomberCat Dashboard - Interfaz web para monitoreo y control
"""

import flet as ft
import logging
import sys
import os
import time
import asyncio
from typing import Optional

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Agregar el directorio padre al path para importaciones
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones locales
try:
    from ui.state import StateManager, LogEntry, LogLevel, SystemStatus
    from ui.components.dashboard_view import DashboardView
    from ui.websocket_manager import WSManager
except ImportError as e:
    logger.error(f"Error importando módulos: {e}")
    sys.exit(1)


class SimpleDashboard:
    """Dashboard simplificado para BomberCat."""
    
    def __init__(self):
        self.page: Optional[ft.Page] = None
        self.state_manager = StateManager()
        self.ws_manager: Optional[WSManager] = None
        self.dashboard_view: Optional[DashboardView] = None
        
    def initialize(self, page: ft.Page):
        """Inicializa el dashboard (versión síncrona - deprecated)."""
        logger.warning("Usando initialize síncrono - se recomienda usar initialize_async")
        asyncio.run(self.initialize_async(page))
        
    async def initialize_async(self, page: ft.Page):
        """Inicializa el dashboard de forma asíncrona."""
        print("🔄 [DEBUG] Inicializando dashboard async...")
        logger.info("Inicializando dashboard async...")
        
        self.page = page
        
        # Configurar página
        page.title = "BomberCat Dashboard"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        page.spacing = 0
        
        # Configurar tema
        page.theme = ft.Theme(
            color_scheme_seed=ft.colors.BLUE,
            use_material3=True,
        )
        
        # Configurar ventana
        page.window_width = 1200
        page.window_height = 800
        page.window_min_width = 800
        page.window_min_height = 600
        
        # Crear WebSocket manager
        self.ws_manager = WSManager("ws://localhost:8001/ws")
        
        # Crear vista del dashboard
        self.dashboard_view = DashboardView(self.state_manager, self.ws_manager)
        
        # Agregar log inicial
        initial_log = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            message="Dashboard iniciado correctamente",
            source="app"
        )
        self.state_manager.add_log_entry(initial_log)
        
        # Intentar conectar WebSocket con timeout de 1 segundo
        await self._try_websocket_connection_with_timeout()
        
        print("✅ [DEBUG] Dashboard inicializado correctamente")
        logger.info("Dashboard inicializado correctamente")
        
    async def _try_websocket_connection_with_timeout(self):
        """Intenta conectar al WebSocket con timeout de 1 segundo."""
        print("🔄 [DEBUG] Intentando conexión WebSocket con timeout...")
        
        try:
            # Intentar conectar con timeout de 1 segundo
            connection_task = asyncio.create_task(self._connect_websocket())
            await asyncio.wait_for(connection_task, timeout=1.0)
            
        except asyncio.TimeoutError:
            logger.warning("Timeout conectando WebSocket - mostrando banner offline")
            print("⚠️ [DEBUG] Timeout WebSocket - mostrando banner offline")
            self._show_backend_offline_banner()
            
        except Exception as e:
            logger.warning(f"Error conectando WebSocket: {e}")
            print(f"⚠️ [DEBUG] Error WebSocket: {e}")
            self._show_backend_offline_banner()
            
    def _show_backend_offline_banner(self):
        """Muestra banner de backend offline."""
        if self.page:
            offline_banner = ft.Banner(
                bgcolor=ft.colors.ORANGE_100,
                leading=ft.Icon(ft.icons.WIFI_OFF, color=ft.colors.ORANGE, size=40),
                content=ft.Text(
                    "⚠️ Backend offline - Ejecutando en modo local. Inicia el backend para funcionalidad completa.",
                    color=ft.colors.ORANGE_800
                ),
                actions=[
                    ft.TextButton("Reintentar", on_click=lambda _: self._retry_connection()),
                    ft.TextButton("Cerrar", on_click=lambda _: self.page.close_banner())
                ]
            )
            self.page.banner = offline_banner
            self.page.open_banner()
            self.page.update()
            
        # Agregar log de modo offline
        offline_log = LogEntry(
            timestamp=time.time(),
            level=LogLevel.WARNING,
            message="Ejecutando en modo offline - Backend no disponible",
            source="websocket"
        )
        self.state_manager.add_log_entry(offline_log)
        
    def _retry_connection(self):
        """Reintenta la conexión WebSocket."""
        print("🔄 [DEBUG] Reintentando conexión WebSocket...")
        asyncio.create_task(self._try_websocket_connection_with_timeout())
        
    def _try_websocket_connection(self):
        """Intenta conectar al WebSocket de forma no bloqueante (método legacy)."""
        try:
            # Crear tarea para conectar en background
            asyncio.create_task(self._connect_websocket())
        except Exception as e:
            logger.warning(f"No se pudo iniciar conexión WebSocket: {e}")
            self._show_backend_offline_banner()
            
    async def _connect_websocket(self):
        """Conecta al WebSocket de forma asíncrona."""
        try:
            if await self.ws_manager.connect():
                self.state_manager.update_websocket_status(True)
                
                success_log = LogEntry(
                    timestamp=time.time(),
                    level=LogLevel.INFO,
                    message="Conectado al backend exitosamente",
                    source="websocket"
                )
                self.state_manager.add_log_entry(success_log)
                
                # Suscribirse a mensajes
                self.ws_manager.subscribe(self._handle_websocket_message)
                
            else:
                self.state_manager.update_websocket_status(False)
                
                error_log = LogEntry(
                    timestamp=time.time(),
                    level=LogLevel.ERROR,
                    message="No se pudo conectar al backend",
                    source="websocket"
                )
                self.state_manager.add_log_entry(error_log)
                
        except Exception as e:
            logger.error(f"Error conectando WebSocket: {e}")
            self.state_manager.update_websocket_status(False)
            
    def _handle_websocket_message(self, message):
        """Maneja mensajes del WebSocket."""
        try:
            logger.debug(f"Mensaje WebSocket recibido: {message.type}")
            # Aquí se procesarían los diferentes tipos de mensajes
            # Por ahora solo loggeamos que se recibió
            
        except Exception as e:
            logger.error(f"Error procesando mensaje WebSocket: {e}")


async def dashboard_app(page: ft.Page):
    """Función principal del dashboard (async)."""
    print("🔄 [DEBUG] Entrando a dashboard_app...")
    logger.info("🔄 Entrando a dashboard_app...")
    
    try:
        logger.info("Iniciando aplicación dashboard...")
        print("🔄 [DEBUG] Iniciando aplicación dashboard...")
        
        # Agregar widget de confirmación de carga UI
        loading_indicator = ft.Container(
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text("Cargando Dashboard...", size=16)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True
        )
        page.add(loading_indicator)
        page.update()
        print("🔄 [DEBUG] Loading indicator agregado")
        
        # Crear y inicializar dashboard
        dashboard = SimpleDashboard()
        await dashboard.initialize_async(page)
        
        # Remover loading indicator y mostrar dashboard
        page.clean()
        page.add(dashboard.dashboard_view)
        
        # Agregar widget de confirmación de que la UI se cargó
        ui_loaded_banner = ft.Banner(
            bgcolor=ft.colors.GREEN_100,
            leading=ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN, size=40),
            content=ft.Text("✅ UI loaded - Dashboard cargado correctamente", color=ft.colors.GREEN_800),
            actions=[
                ft.TextButton("OK", on_click=lambda _: page.close_banner())
            ]
        )
        page.banner = ui_loaded_banner
        page.open_banner()
        page.update()
        
        logger.info("Dashboard iniciado exitosamente")
        print("✅ [DEBUG] Dashboard iniciado exitosamente")
        
    except Exception as e:
        logger.error(f"Error crítico en dashboard: {e}")
        print(f"❌ [DEBUG] Error crítico en dashboard: {e}")
        
        # Mostrar error en la página
        try:
            page.clean()
            error_container = ft.Container(
                content=ft.Column([
                    ft.Text("🚨 Error del Dashboard", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.RED),
                    ft.Text(f"Error: {str(e)}", size=16),
                    ft.Text("Revisa los logs para más detalles.", size=14, color=ft.colors.GREY_400)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                expand=True,
                padding=20
            )
            page.add(error_container)
            page.update()
        except Exception as display_error:
            logger.error(f"Error mostrando mensaje de error: {display_error}")
    
    print("🔄 [DEBUG] Saliendo de dashboard_app...")
    logger.info("🔄 Saliendo de dashboard_app...")


async def main_async():
    """Función principal asíncrona."""
    try:
        logger.info("Iniciando aplicación BomberCat Dashboard...")
        print("🚀 [DEBUG] Iniciando aplicación BomberCat Dashboard...")
        
        await ft.app_async(
            target=dashboard_app,
            name="bombercat-dashboard",
            port=8550,
            view=ft.AppView.WEB_BROWSER,
            web_renderer=ft.WebRenderer.HTML,
        )
        
    except KeyboardInterrupt:
        logger.info("Aplicación interrumpida por usuario")
        print("⏹️ [DEBUG] Aplicación interrumpida por usuario")
    except Exception as e:
        logger.error(f"Error ejecutando aplicación: {e}")
        print(f"❌ [DEBUG] Error ejecutando aplicación: {e}")
        sys.exit(1)
        
def main():
    """Función principal que ejecuta la versión async."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()