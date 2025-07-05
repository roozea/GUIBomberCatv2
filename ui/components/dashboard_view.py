"""Vista principal del dashboard con layout responsive.

Implementa un layout adaptativo que se ajusta a diferentes
tamaños de pantalla: móvil, tablet y desktop.
"""

import flet as ft
import asyncio
import logging
from typing import Optional

from ui.state import StateManager, BomberCatState, LogLevel
from ui.websocket_manager import WSManager
from .latency_chart import LatencyChart
from .control_panel import ControlPanel


class DashboardView(ft.Container):
    """Vista principal del dashboard con layout responsive."""
    
    def __init__(self, state_manager: StateManager, ws_manager: WSManager):
        """Inicializa la vista del dashboard.
        
        Args:
            state_manager: Manager del estado global
            ws_manager: Manager de WebSocket
        """
        self.state_manager = state_manager
        self.ws_manager = ws_manager
        self.logger = logging.getLogger(__name__)
        
        # Componentes
        self.latency_chart: Optional[LatencyChart] = None
        self.control_panel: Optional[ControlPanel] = None
        self.logs_view: Optional[ft.ListView] = None
        self.metrics_cards: Optional[ft.Row] = None
        self.theme_toggle: Optional[ft.IconButton] = None
        
        # Estado interno
        self.current_state: Optional[BomberCatState] = None
        
        # Inicializar Container con el contenido
        super().__init__(
            content=self._build_content(),
            expand=True
        )
        
    def _build_content(self):
        """Construye el contenido del componente UI con layout responsive."""
        # Crear componentes principales
        self.latency_chart = LatencyChart(self.state_manager)
        self.control_panel = ControlPanel(self.state_manager, self.ws_manager)
        
        # Toggle de tema
        self.theme_toggle = ft.IconButton(
            icon=ft.icons.DARK_MODE,
            tooltip="Cambiar tema",
            on_click=self._toggle_theme,
        )
        
        # Banner de estado de conexión
        self.connection_banner = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.WIFI_OFF, color=ft.colors.WHITE, size=16),
                ft.Text(
                    "Backend offline - Modo de prueba activo",
                    color=ft.colors.WHITE,
                    size=14,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(expand=True),
                ft.TextButton(
                    "Reconectar",
                    style=ft.ButtonStyle(
                        color=ft.colors.WHITE,
                        overlay_color=ft.colors.with_opacity(0.1, ft.colors.WHITE)
                    ),
                    on_click=self._reconnect_websocket
                )
            ]),
            bgcolor=ft.colors.RED_600,
            padding=ft.padding.symmetric(horizontal=20, vertical=8),
            visible=False  # Inicialmente oculto
        )
        
        # Header con título y controles
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        "BomberCat Dashboard",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.PRIMARY,
                    ),
                    ft.Container(expand=True),  # Spacer
                    self.theme_toggle,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
            bgcolor=ft.colors.with_opacity(0.05, ft.colors.SURFACE_VARIANT),
        )
        
        # Tarjetas de métricas
        self.metrics_cards = self._create_metrics_cards()
        
        # Vista de logs
        self.logs_view = self._create_logs_view()
        
        # Layout responsive principal
        main_content = ft.ResponsiveRow(
            [
                # Panel de control (izquierda en desktop, arriba en móvil)
                ft.Container(
                    content=self.control_panel,
                    col={"sm": 12, "md": 12, "lg": 4},  # 100% móvil/tablet, 33% desktop
                ),
                
                # Contenido principal (derecha en desktop, abajo en móvil)
                ft.Container(
                    content=ft.Column(
                        [
                            # Métricas del sistema
                            self.metrics_cards,
                            
                            # Gráfico de latencia
                            ft.Container(
                                content=self.latency_chart,
                                col={"sm": 12, "md": 12, "lg": 12},
                            ),
                            
                            # Vista de logs
                            ft.Container(
                                content=self.logs_view,
                                col={"sm": 12, "md": 12, "lg": 12},
                            ),
                        ],
                        spacing=16,
                    ),
                    col={"sm": 12, "md": 12, "lg": 8},  # 100% móvil/tablet, 67% desktop
                ),
            ],
            spacing=16,
        )
        
        return ft.Column(
            [
                self.connection_banner,  # Banner de estado de conexión
                header,
                ft.Container(
                    content=main_content,
                    padding=ft.padding.all(20),
                    expand=True,
                ),
            ],
            spacing=0,
        )
        
    def did_mount(self):
        """Se ejecuta cuando el componente se monta."""
        # Suscribirse a cambios de estado
        self.state_manager.add_listener('all', self._on_state_update)
        
        # Cargar estado inicial
        self.current_state = self.state_manager.get_state()
        self._update_ui()
        
        # Aplicar tema inicial
        self._apply_theme()
        
    def will_unmount(self):
        """Se ejecuta cuando el componente se desmonta."""
        # Desuscribirse de eventos
        self.state_manager.remove_listener('all', self._on_state_update)
        
    def _create_metrics_cards(self) -> ft.ResponsiveRow:
        """Crea las tarjetas de métricas del sistema."""
        return ft.ResponsiveRow(
            [
                # Tarjeta de paquetes relay
                ft.Container(
                    content=self._create_metric_card(
                        "Paquetes Relay",
                        "0",
                        ft.icons.SWAP_HORIZ,
                        ft.colors.BLUE_600,
                        "packets"
                    ),
                    col={"sm": 6, "md": 3, "lg": 3},
                ),
                
                # Tarjeta de errores
                ft.Container(
                    content=self._create_metric_card(
                        "Errores",
                        "0",
                        ft.icons.ERROR_OUTLINE,
                        ft.colors.RED_600,
                        "errors"
                    ),
                    col={"sm": 6, "md": 3, "lg": 3},
                ),
                
                # Tarjeta de CPU
                ft.Container(
                    content=self._create_metric_card(
                        "CPU",
                        "0%",
                        ft.icons.MEMORY,
                        ft.colors.GREEN_600,
                        "cpu"
                    ),
                    col={"sm": 6, "md": 3, "lg": 3},
                ),
                
                # Tarjeta de memoria
                ft.Container(
                    content=self._create_metric_card(
                        "Memoria",
                        "0%",
                        ft.icons.STORAGE,
                        ft.colors.ORANGE_600,
                        "memory"
                    ),
                    col={"sm": 6, "md": 3, "lg": 3},
                ),
            ],
            spacing=12,
        )
        
    def _create_metric_card(self, title: str, value: str, icon: str, 
                           color: str, metric_id: str) -> ft.Container:
        """Crea una tarjeta de métrica individual."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=color, size=24),
                            ft.Container(expand=True),
                        ],
                    ),
                    ft.Text(
                        value,
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        data=metric_id,  # Para identificar en actualizaciones
                    ),
                    ft.Text(
                        title,
                        size=12,
                        color=ft.colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(16),
            border_radius=12,
            bgcolor=ft.colors.with_opacity(0.05, ft.colors.SURFACE_VARIANT),
            border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.OUTLINE)),
        )
        
    def _create_logs_view(self) -> ft.Container:
        """Crea la vista de logs del sistema."""
        self.logs_list = ft.ListView(
            spacing=4,
            padding=ft.padding.all(8),
            auto_scroll=True,
            height=200,
        )
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Logs del Sistema",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.icons.CLEAR_ALL,
                                tooltip="Limpiar logs",
                                on_click=self._clear_logs,
                            ),
                        ],
                    ),
                    ft.Container(
                        content=self.logs_list,
                        border_radius=8,
                        bgcolor=ft.colors.with_opacity(0.02, ft.colors.ON_SURFACE),
                        border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.OUTLINE)),
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(16),
            border_radius=12,
            bgcolor=ft.colors.with_opacity(0.05, ft.colors.SURFACE_VARIANT),
        )
        
    def _on_state_update(self, state: BomberCatState):
        """Callback para actualizaciones de estado."""
        self.current_state = state
        
        # Actualizar banner de conexión según el estado WebSocket
        if hasattr(state, 'websocket_connected'):
            if state.websocket_connected:
                self._update_connection_banner("connected")
            else:
                self._update_connection_banner("disconnected")
        
        self._update_ui()
        
    def _update_ui(self):
        """Actualiza la interfaz según el estado actual."""
        if not self.current_state:
            return
            
        try:
            # Actualizar métricas
            self._update_metrics()
            
            # Actualizar logs
            self._update_logs()
            
            # Actualizar tema si cambió
            self._apply_theme()
            
            # Forzar actualización de UI
            if self.page:
                self.update()
                
        except Exception as e:
            self.logger.error(f"Error actualizando UI del dashboard: {e}")
            
    def _update_metrics(self):
        """Actualiza las tarjetas de métricas."""
        if not self.current_state or not self.metrics_cards:
            return
            
        # Buscar y actualizar cada métrica
        for container in self.metrics_cards.controls:
            if isinstance(container, ft.Container):
                card = container.content
                if isinstance(card, ft.Column) and len(card.controls) >= 2:
                    value_text = card.controls[1]
                    if isinstance(value_text, ft.Text) and hasattr(value_text, 'data'):
                        metric_id = value_text.data
                        
                        if metric_id == "packets":
                            total = (self.current_state.relay_packets_sent + 
                                   self.current_state.relay_packets_received)
                            value_text.value = str(total)
                        elif metric_id == "errors":
                            value_text.value = str(self.current_state.relay_errors)
                        elif metric_id == "cpu":
                            value_text.value = f"{self.current_state.cpu_usage:.1f}%"
                        elif metric_id == "memory":
                            value_text.value = f"{self.current_state.memory_usage:.1f}%"
                            
    def _update_logs(self):
        """Actualiza la vista de logs."""
        if not self.current_state or not hasattr(self, 'logs_list'):
            return
            
        # Limpiar logs actuales
        self.logs_list.controls.clear()
        
        # Agregar logs recientes (últimos 50)
        recent_logs = list(self.current_state.logs)[-50:]
        
        for log_entry in recent_logs:
            # Color según nivel de log
            color_map = {
                LogLevel.DEBUG: ft.colors.GREY_600,
                LogLevel.INFO: ft.colors.BLUE_600,
                LogLevel.WARNING: ft.colors.ORANGE_600,
                LogLevel.ERROR: ft.colors.RED_600,
            }
            
            color = color_map.get(log_entry.level, ft.colors.ON_SURFACE)
            
            log_row = ft.Row(
                [
                    ft.Text(
                        log_entry.timestamp.strftime("%H:%M:%S"),
                        size=10,
                        color=ft.colors.ON_SURFACE_VARIANT,
                        width=60,
                    ),
                    ft.Text(
                        log_entry.level.value.upper(),
                        size=10,
                        color=color,
                        weight=ft.FontWeight.BOLD,
                        width=50,
                    ),
                    ft.Text(
                        f"[{log_entry.component}]",
                        size=10,
                        color=ft.colors.ON_SURFACE_VARIANT,
                        width=80,
                    ),
                    ft.Text(
                        log_entry.message,
                        size=10,
                        color=ft.colors.ON_SURFACE,
                        expand=True,
                    ),
                ],
                spacing=8,
            )
            
            self.logs_list.controls.append(log_row)
            
    def _apply_theme(self):
        """Aplica el tema actual."""
        if not self.current_state or not self.theme_toggle:
            return
            
        if self.current_state.dark_theme:
            self.theme_toggle.icon = ft.icons.LIGHT_MODE
            self.theme_toggle.tooltip = "Cambiar a tema claro"
        else:
            self.theme_toggle.icon = ft.icons.DARK_MODE
            self.theme_toggle.tooltip = "Cambiar a tema oscuro"
            
    def _toggle_theme(self, e):
        """Alterna el tema de la aplicación."""
        asyncio.create_task(self.state_manager.toggle_theme())
        
    def _clear_logs(self, e):
        """Limpia los logs del sistema."""
        asyncio.create_task(self._async_clear_logs())
        
    async def _async_clear_logs(self):
        """Limpia los logs de forma asíncrona."""
        if hasattr(self, 'logs_list'):
            self.logs_list.controls.clear()
            
        # Limpiar logs del estado
        async with self.state_manager._lock:
            self.state_manager.state.logs.clear()
            
        await self.state_manager.add_log(
            LogLevel.INFO,
            "Logs limpiados",
            "dashboard"
        )
        
        if self.page:
            self.update()
            
    async def _reconnect_websocket(self, e):
        """Intenta reconectar el WebSocket."""
        try:
            # Mostrar estado de reconexión
            self._update_connection_banner("connecting")
            
            # Intentar reconectar
            if await self.ws_manager.connect():
                self.logger.info("Reconexión WebSocket exitosa")
                self._update_connection_banner("connected")
                
                # Agregar log de éxito
                await self.state_manager.add_log(
                    LogLevel.INFO,
                    "Reconexión WebSocket exitosa",
                    "websocket"
                )
            else:
                self.logger.error("Falló la reconexión WebSocket")
                self._update_connection_banner("disconnected")
                
                # Agregar log de error
                await self.state_manager.add_log(
                    LogLevel.ERROR,
                    "Falló la reconexión WebSocket",
                    "websocket"
                )
                
        except Exception as ex:
            self.logger.error(f"Error durante reconexión: {ex}")
            self._update_connection_banner("disconnected")
            
            # Agregar log de excepción
            await self.state_manager.add_log(
                LogLevel.ERROR,
                f"Error durante reconexión: {str(ex)}",
                "websocket"
            )
            
    def _update_connection_banner(self, status: str):
        """Actualiza el banner de estado de conexión.
        
        Args:
            status: Estado de conexión ('connected', 'disconnected', 'connecting')
        """
        if not hasattr(self, 'connection_banner'):
            return
            
        banner_content = self.connection_banner.content
        if not isinstance(banner_content, ft.Row) or len(banner_content.controls) < 2:
            return
            
        icon_control = banner_content.controls[0]
        text_control = banner_content.controls[1]
        
        if status == "connected":
            self.connection_banner.visible = False
            self.connection_banner.bgcolor = ft.colors.GREEN_600
            icon_control.name = ft.icons.WIFI
            text_control.value = "Backend conectado"
            
        elif status == "connecting":
            self.connection_banner.visible = True
            self.connection_banner.bgcolor = ft.colors.BLUE_600
            icon_control.name = ft.icons.WIFI_FIND
            text_control.value = "Conectando al backend..."
            
        elif status == "disconnected":
            self.connection_banner.visible = True
            self.connection_banner.bgcolor = ft.colors.RED_600
            icon_control.name = ft.icons.WIFI_OFF
            text_control.value = "Backend offline - Modo de prueba activo"
            
        # Actualizar UI
        if self.page:
            self.update()
