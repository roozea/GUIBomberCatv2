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
            color_scheme_seed=ft.Colors.BLUE,
            use_material3=True,
        )
        
        # Configurar ventana
        page.window_width = 1200
        page.window_height = 800
        page.window_min_width = 800
        page.window_min_height = 600
        
        # Crear WebSocket manager
        self.ws_manager = WSManager("ws://localhost:8000/ws")
        
        # Crear vista del dashboard
        self.dashboard_view = DashboardView(self.state_manager, self.ws_manager)
        
        # Agregar log inicial
        await self.state_manager.add_log(
            LogLevel.INFO,
            "Dashboard iniciado correctamente",
            "app"
        )
        
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
            await asyncio.wait_for(connection_task, timeout=2.0)
            
        except asyncio.TimeoutError:
            logger.warning("Timeout conectando WebSocket - mostrando banner offline")
            print("⚠️ [DEBUG] Timeout WebSocket - mostrando banner offline")
            await self._show_backend_offline_banner()
            
        except Exception as e:
            logger.warning(f"Error conectando WebSocket: {e}")
            print(f"⚠️ [DEBUG] Error WebSocket: {e}")
            await self._show_backend_offline_banner()
            
    async def _show_backend_offline_banner(self):
        """Muestra banner de backend offline."""
        if self.page:
            offline_banner = ft.Banner(
                bgcolor=ft.Colors.ORANGE_100,
                leading=ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.ORANGE, size=40),
                content=ft.Text(
                    "⚠️ Backend offline - Ejecutando en modo local. Inicia el backend para funcionalidad completa.",
                    color=ft.Colors.ORANGE_800
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
        await self.state_manager.add_log(
            LogLevel.WARNING,
            "Ejecutando en modo offline - Backend no disponible",
            "websocket"
        )
        
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
            asyncio.create_task(self._show_backend_offline_banner())
            
    async def _connect_websocket(self):
        """Conecta al WebSocket de forma asíncrona."""
        try:
            if await self.ws_manager.connect():
                await self.state_manager.update_websocket_status(True)
                
                await self.state_manager.add_log(
                    LogLevel.INFO,
                    "Conectado al backend exitosamente",
                    "websocket"
                )
                
                # Suscribirse a mensajes
                self.ws_manager.subscribe(self._handle_websocket_message)
                
            else:
                await self.state_manager.update_websocket_status(False)
                
                await self.state_manager.add_log(
                    LogLevel.ERROR,
                    "No se pudo conectar al backend",
                    "websocket"
                )
                
        except Exception as e:
            logger.error(f"Error conectando WebSocket: {e}")
            await self.state_manager.update_websocket_status(False)
            
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
    try:
        print("🚀 UI init start")
        logger.info("🚀 UI init start")
        
        # Configurar página básica
        page.title = "BomberCat Dashboard"
        page.theme_mode = ft.ThemeMode.DARK
        
        print("📄 [DEBUG] Página configurada")
        logger.info("📄 Página configurada")
        
        # Mostrar mensaje HELLO simple
        hello_text = ft.Text(
            "HELLO",
            size=48,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN,
            text_align=ft.TextAlign.CENTER
        )
        
        print("📝 [DEBUG] Texto HELLO creado")
        logger.info("📝 Texto HELLO creado")
        
        page.add(
            ft.Container(
                content=hello_text,
                alignment=ft.alignment.center,
                expand=True
            )
        )
        
        print("➕ [DEBUG] Contenido agregado a página")
        logger.info("➕ Contenido agregado a página")
        
        page.update()
        print("✅ [DEBUG] Dashboard con HELLO mostrado")
        logger.info("✅ Dashboard con HELLO mostrado")
        
    except Exception as e:
        print(f"❌ [ERROR] Exception in dashboard_app: {e}")
        logger.error(f"❌ Exception in dashboard_app: {e}")
        import traceback
        traceback.print_exc()
        
        # Mostrar error en la página si es posible
        try:
            page.add(ft.Text(f"Error: {str(e)}", color=ft.Colors.RED))
            page.update()
        except Exception as page_error:
            print(f"❌ [ERROR] Could not show error on page: {page_error}")
            logger.error(f"❌ Could not show error on page: {page_error}")


if __name__ == "__main__":
    logger.info("Iniciando aplicación BomberCat Dashboard...")
    print("🚀 [DEBUG] Iniciando aplicación BomberCat Dashboard...")
    
    print("📋 [DEBUG] Registering app with target=dashboard_app")
    logger.info("📋 Registering app with target=dashboard_app")
    
    try:
        asyncio.run(ft.app_async(
            target=dashboard_app,
            name="",
            port=8550,
            view=ft.AppView.WEB_BROWSER,
            web_renderer=ft.WebRenderer.CANVAS_KIT,
        ))
    except Exception as e:
        print(f"❌ [ERROR] Exception in ft.app_async: {e}")
        logger.error(f"❌ Exception in ft.app_async: {e}")
        import traceback
        traceback.print_exc()
