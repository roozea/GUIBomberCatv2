"""Panel de control para el dashboard BomberCat.

Proporciona controles para flashear dispositivos, iniciar/detener
el relay y otras operaciones del sistema.
"""

import flet as ft
import asyncio
import logging
from typing import Optional, Callable

from ui.state import StateManager, BomberCatState, SystemStatus, LogLevel
from ui.websocket_manager import WSManager


class ControlPanel(ft.Container):
    """Panel de control principal del dashboard."""
    
    def __init__(self, state_manager: StateManager, ws_manager: WSManager):
        """Inicializa el panel de control.
        
        Args:
            state_manager: Manager del estado global
            ws_manager: Manager de WebSocket para enviar comandos
        """
        self.state_manager = state_manager
        self.ws_manager = ws_manager
        self.logger = logging.getLogger(__name__)
        
        # Componentes UI
        self.flash_button: Optional[ft.ElevatedButton] = None
        self.relay_start_button: Optional[ft.ElevatedButton] = None
        self.relay_stop_button: Optional[ft.ElevatedButton] = None
        self.device_scan_button: Optional[ft.IconButton] = None
        self.status_indicator: Optional[ft.Container] = None
        self.device_info_text: Optional[ft.Text] = None
        self.connection_status: Optional[ft.Text] = None
        
        # Estado interno
        self.current_state: Optional[BomberCatState] = None
        
        # Inicializar Container con el contenido
        super().__init__(
            content=self._build_content(),
            padding=ft.padding.all(16)
        )
        
    def _build_content(self):
        """Construye el contenido del componente UI."""
        # Botón de flasheo
        self.flash_button = ft.ElevatedButton(
            text="Flash Device",
            icon=ft.Icons.FLASH_ON,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.ORANGE_600,
            ),
            on_click=self._on_flash_click,
            disabled=True,
        )
        
        # Botones de relay
        self.relay_start_button = ft.ElevatedButton(
            text="Start Relay",
            icon=ft.Icons.PLAY_ARROW,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN_600,
            ),
            on_click=self._on_relay_start_click,
            disabled=True,
        )
        
        self.relay_stop_button = ft.ElevatedButton(
            text="Stop Relay",
            icon=ft.Icons.STOP,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.RED_600,
            ),
            on_click=self._on_relay_stop_click,
            disabled=True,
        )
        
        # Botón de escaneo de dispositivos
        self.device_scan_button = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Escanear dispositivos",
            on_click=self._on_device_scan_click,
        )
        
        # Indicador de estado
        self.status_indicator = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CIRCLE,
                        color=ft.Colors.GREY_400,
                        size=12,
                    ),
                    ft.Text(
                        "Inactivo",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            border_radius=16,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY_100),
        )
        
        # Información del dispositivo
        self.device_info_text = ft.Text(
            "Sin dispositivo conectado",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # Estado de conexión WebSocket
        self.connection_status = ft.Text(
            "WebSocket: Desconectado",
            size=10,
            color=ft.Colors.ERROR,
        )
        
        # Sección de dispositivo
        device_section = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Dispositivo",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(expand=True),
                            self.device_scan_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self.device_info_text,
                    ft.Divider(height=1),
                    self.flash_button,
                ],
                spacing=8,
            ),
            padding=ft.padding.all(16),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREY_100),
        )
        
        # Sección de relay
        relay_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Relay NFC",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Row(
                        [
                            self.relay_start_button,
                            self.relay_stop_button,
                        ],
                        spacing=8,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(16),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREY_100),
        )
        
        # Sección de estado
        status_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Estado del Sistema",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                    ),
                    self.status_indicator,
                    self.connection_status,
                ],
                spacing=8,
            ),
            padding=ft.padding.all(16),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREY_100),
        )
        
        return ft.Column(
            [
                ft.Text(
                    "Panel de Control",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                device_section,
                relay_section,
                status_section,
            ],
            spacing=16,
        )
        
    def did_mount(self):
        """Se ejecuta cuando el componente se monta."""
        # Suscribirse a cambios de estado
        self.state_manager.add_listener('all', self._on_state_update)
        
        # Cargar estado inicial
        self.current_state = self.state_manager.get_state()
        self._update_ui()
        
    def will_unmount(self):
        """Se ejecuta cuando el componente se desmonta."""
        # Desuscribirse de eventos
        self.state_manager.remove_listener('all', self._on_state_update)
        
    def _on_state_update(self, state: BomberCatState):
        """Callback para actualizaciones de estado."""
        self.current_state = state
        self._update_ui()
        
    def _update_ui(self):
        """Actualiza la interfaz según el estado actual."""
        if not self.current_state:
            return
            
        try:
            # Actualizar botones según el estado
            self._update_buttons()
            
            # Actualizar indicador de estado
            self._update_status_indicator()
            
            # Actualizar información del dispositivo
            self._update_device_info()
            
            # Actualizar estado de conexión
            self._update_connection_status()
            
            # Forzar actualización de UI
            if self.page:
                self.update()
                
        except Exception as e:
            self.logger.error(f"Error actualizando UI del panel de control: {e}")
            
    def _update_buttons(self):
        """Actualiza el estado de los botones."""
        if not self.current_state:
            return
            
        # Estado del dispositivo
        device_connected = self.current_state.device.connected
        is_flashing = self.current_state.status == SystemStatus.FLASHING
        is_relay_running = self.current_state.relay_running
        websocket_connected = self.current_state.websocket_connected
        
        # Botón de flash: habilitado si hay dispositivo y no está flasheando
        if self.flash_button:
            self.flash_button.disabled = (
                not device_connected or 
                is_flashing or 
                not websocket_connected
            )
            self.flash_button.text = "Flasheando..." if is_flashing else "Flash Device"
            
        # Botón start relay: habilitado si no está corriendo y WS conectado
        if self.relay_start_button:
            self.relay_start_button.disabled = (
                is_relay_running or 
                not websocket_connected or
                is_flashing
            )
            
        # Botón stop relay: habilitado si está corriendo
        if self.relay_stop_button:
            self.relay_stop_button.disabled = not is_relay_running
            
    def _update_status_indicator(self):
        """Actualiza el indicador de estado del sistema."""
        if not self.current_state or not self.status_indicator:
            return
            
        status = self.current_state.status
        
        # Mapear estado a color e icono
        status_config = {
            SystemStatus.IDLE: (ft.Colors.GREY_400, "Inactivo"),
            SystemStatus.FLASHING: (ft.Colors.ORANGE_600, "Flasheando"),
            SystemStatus.RELAY_RUNNING: (ft.Colors.GREEN_600, "Relay Activo"),
            SystemStatus.ERROR: (ft.Colors.RED_600, "Error"),
            SystemStatus.CONNECTING: (ft.Colors.BLUE_600, "Conectando"),
        }
        
        color, text = status_config.get(status, (ft.Colors.GREY_400, "Desconocido"))
        
        # Actualizar contenido del indicador
        row = self.status_indicator.content
        if isinstance(row, ft.Row) and len(row.controls) >= 2:
            row.controls[0].color = color  # Icono
            row.controls[1].value = text   # Texto
            
    def _update_device_info(self):
        """Actualiza la información del dispositivo."""
        if not self.current_state or not self.device_info_text:
            return
            
        device = self.current_state.device
        
        if device.connected and device.port:
            info_parts = [f"Puerto: {device.port}"]
            if device.chip_type:
                info_parts.append(f"Chip: {device.chip_type}")
            if device.mac_address:
                info_parts.append(f"MAC: {device.mac_address}")
                
            self.device_info_text.value = " | ".join(info_parts)
            self.device_info_text.color = ft.Colors.ON_SURFACE
        else:
            self.device_info_text.value = "Sin dispositivo conectado"
            self.device_info_text.color = ft.Colors.ON_SURFACE_VARIANT
            
    def _update_connection_status(self):
        """Actualiza el estado de conexión WebSocket."""
        if not self.current_state or not self.connection_status:
            return
            
        if self.current_state.websocket_connected:
            self.connection_status.value = "WebSocket: Conectado"
            self.connection_status.color = ft.Colors.GREEN_600
        else:
            self.connection_status.value = "WebSocket: Desconectado"
            self.connection_status.color = ft.Colors.ERROR
            
    async def _send_command(self, command: str, data: dict = None):
        """Envía un comando por WebSocket.
        
        Args:
            command: Comando a enviar
            data: Datos adicionales del comando
        """
        if not self.ws_manager.connected:
            await self.state_manager.add_log(
                LogLevel.ERROR,
                "No se puede enviar comando: WebSocket desconectado",
                "control_panel"
            )
            return False
            
        message = {
            "cmd": command,
            "data": data or {}
        }
        
        success = await self.ws_manager.send(message)
        
        if success:
            await self.state_manager.add_log(
                LogLevel.INFO,
                f"Comando enviado: {command}",
                "control_panel"
            )
        else:
            await self.state_manager.add_log(
                LogLevel.ERROR,
                f"Error enviando comando: {command}",
                "control_panel"
            )
            
        return success
        
    def _on_flash_click(self, e):
        """Maneja click en botón de flash."""
        asyncio.create_task(self._handle_flash_command())
        
    async def _handle_flash_command(self):
        """Maneja el comando de flasheo."""
        await self._send_command("flash")
        
    def _on_relay_start_click(self, e):
        """Maneja click en botón de start relay."""
        asyncio.create_task(self._handle_relay_start_command())
        
    async def _handle_relay_start_command(self):
        """Maneja el comando de inicio de relay."""
        await self._send_command("relay_start")
        
    def _on_relay_stop_click(self, e):
        """Maneja click en botón de stop relay."""
        asyncio.create_task(self._handle_relay_stop_command())
        
    async def _handle_relay_stop_command(self):
        """Maneja el comando de parada de relay."""
        await self._send_command("relay_stop")
        
    def _on_device_scan_click(self, e):
        """Maneja click en botón de escaneo de dispositivos."""
        asyncio.create_task(self._handle_device_scan_command())
        
    async def _handle_device_scan_command(self):
        """Maneja el comando de escaneo de dispositivos."""
        await self._send_command("device_scan")
