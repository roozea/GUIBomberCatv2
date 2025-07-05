"""Componente de gráfico de latencia para el dashboard.

Implementa un gráfico de líneas en tiempo real para mostrar
la latencia del sistema con buffer circular de 100 puntos.
"""

import flet as ft
from typing import List, Optional
from collections import deque
import asyncio
import logging

from ui.state import StateManager, BomberCatState, LatencyPoint


class LatencyChart(ft.Container):
    """Componente de gráfico de latencia en tiempo real."""
    
    def __init__(self, state_manager: StateManager, max_points: int = 100):
        """Inicializa el componente de gráfico de latencia.
        
        Args:
            state_manager: Manager del estado global
            max_points: Número máximo de puntos a mostrar
        """
        self.state_manager = state_manager
        self.max_points = max_points
        self.logger = logging.getLogger(__name__)
        
        # Datos del gráfico
        self.data_points: deque = deque(maxlen=max_points)
        
        # Configuración del gráfico
        self.min_y = 0
        self.max_y = 100  # Latencia máxima inicial en ms
        self.target_latency = 100  # Línea objetivo de latencia
        
        # Componentes UI
        self.chart: Optional[ft.LineChart] = None
        self.stats_text: Optional[ft.Text] = None
        
        # Inicializar Container con el contenido
        super().__init__(
            content=self._build_content(),
            padding=ft.padding.all(16),
            border_radius=12,
            bgcolor=ft.colors.with_opacity(0.05, ft.colors.SURFACE_VARIANT)
        )
        
    def _build_content(self):
        """Construye el contenido del componente UI."""
        # Crear gráfico de líneas
        self.chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=2,
                    color=ft.colors.BLUE_400,
                    curved=True,
                    stroke_cap_round=True,
                )
            ],
            border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.ON_SURFACE)),
            horizontal_grid_lines=ft.ChartGridLines(
                color=ft.colors.with_opacity(0.1, ft.colors.ON_SURFACE),
                width=1,
                dash_pattern=[3, 3],
            ),
            vertical_grid_lines=ft.ChartGridLines(
                color=ft.colors.with_opacity(0.1, ft.colors.ON_SURFACE),
                width=1,
                dash_pattern=[3, 3],
            ),
            left_axis=ft.ChartAxis(
                title=ft.Text("Latencia (ms)", size=12),
                title_size=12,
                labels_size=10,
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Tiempo", size=12),
                title_size=12,
                labels_size=10,
            ),
            tooltip_bgcolor=ft.colors.with_opacity(0.8, ft.colors.BLUE_GREY),
            min_y=self.min_y,
            max_y=self.max_y,
            expand=True,
        )
        
        # Texto de estadísticas
        self.stats_text = ft.Text(
            "Latencia: -- ms | Promedio: -- ms | Máx: -- ms",
            size=12,
            color=ft.colors.ON_SURFACE_VARIANT,
        )
        
        # Controles adicionales
        controls_row = ft.Row(
            [
                ft.IconButton(
                    icon=ft.icons.REFRESH,
                    tooltip="Limpiar gráfico",
                    on_click=self._clear_chart,
                ),
                ft.IconButton(
                    icon=ft.icons.ZOOM_OUT,
                    tooltip="Zoom out",
                    on_click=self._zoom_out,
                ),
                ft.IconButton(
                    icon=ft.icons.ZOOM_IN,
                    tooltip="Zoom in",
                    on_click=self._zoom_in,
                ),
                ft.Container(expand=True),  # Spacer
                self.stats_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        return ft.Column(
            [
                ft.Text(
                    "Latencia del Sistema",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                controls_row,
                ft.Container(
                    content=self.chart,
                    height=300,
                    border_radius=8,
                    bgcolor=ft.colors.with_opacity(0.05, ft.colors.ON_SURFACE),
                ),
            ],
            spacing=10,
        )
        
    def did_mount(self):
        """Se ejecuta cuando el componente se monta."""
        # Suscribirse a cambios de latencia
        self.state_manager.add_listener('latency', self._on_latency_update)
        
        # Cargar datos iniciales
        self._load_initial_data()
        
    def will_unmount(self):
        """Se ejecuta cuando el componente se desmonta."""
        # Desuscribirse de eventos
        self.state_manager.remove_listener('latency', self._on_latency_update)
        
    def add_point(self, latency_ms: float):
        """Agrega un punto de latencia al gráfico.
        
        Args:
            latency_ms: Latencia en milisegundos
        """
        asyncio.create_task(self.state_manager.add_latency_point(latency_ms))
        
    def _on_latency_update(self, state: BomberCatState):
        """Callback para actualizaciones de latencia."""
        try:
            # Actualizar datos locales
            self.data_points = state.latency_data.copy()
            
            # Actualizar gráfico
            self._update_chart()
            
            # Actualizar estadísticas
            self._update_stats()
            
            # Forzar actualización de UI
            if self.page:
                self.update()
                
        except Exception as e:
            self.logger.error(f"Error actualizando gráfico de latencia: {e}")
            
    def _update_chart(self):
        """Actualiza los datos del gráfico."""
        if not self.chart or not self.data_points:
            return
            
        # Convertir puntos a formato del gráfico
        chart_points = []
        base_time = self.data_points[0].timestamp if self.data_points else 0
        
        for i, point in enumerate(self.data_points):
            chart_points.append(
                ft.LineChartDataPoint(
                    x=i,  # Usar índice como X para simplicidad
                    y=point.latency_ms,
                    tooltip=f"{point.latency_ms:.1f} ms",
                )
            )
            
        # Actualizar serie de datos
        self.chart.data_series[0].data_points = chart_points
        
        # Ajustar escala Y automáticamente
        if chart_points:
            latencies = [p.latency_ms for p in self.data_points]
            self.min_y = max(0, min(latencies) - 10)
            self.max_y = max(latencies) + 20
            self.chart.min_y = self.min_y
            self.chart.max_y = self.max_y
            
        # Agregar línea de objetivo si está configurada
        if self.target_latency and self.target_latency <= self.max_y:
            # Crear línea horizontal para objetivo
            target_points = [
                ft.LineChartDataPoint(x=0, y=self.target_latency),
                ft.LineChartDataPoint(x=len(chart_points)-1, y=self.target_latency)
            ]
            
            # Agregar serie para línea objetivo si no existe
            if len(self.chart.data_series) == 1:
                self.chart.data_series.append(
                    ft.LineChartData(
                        data_points=target_points,
                        stroke_width=1,
                        color=ft.colors.RED_400,
                        curved=False,
                        stroke_dash_pattern=[5, 5],
                    )
                )
            else:
                self.chart.data_series[1].data_points = target_points
                
    def _update_stats(self):
        """Actualiza las estadísticas mostradas."""
        if not self.stats_text or not self.data_points:
            return
            
        latencies = [p.latency_ms for p in self.data_points]
        
        if latencies:
            current = latencies[-1]
            average = sum(latencies) / len(latencies)
            maximum = max(latencies)
            
            self.stats_text.value = (
                f"Actual: {current:.1f} ms | "
                f"Promedio: {average:.1f} ms | "
                f"Máx: {maximum:.1f} ms"
            )
        else:
            self.stats_text.value = "Sin datos de latencia"
            
    def _load_initial_data(self):
        """Carga datos iniciales del estado."""
        state = self.state_manager.get_state()
        if state.latency_data:
            self.data_points = state.latency_data.copy()
            self._update_chart()
            self._update_stats()
            
    def _clear_chart(self, e):
        """Limpia el gráfico."""
        asyncio.create_task(self._async_clear_chart())
        
    async def _async_clear_chart(self):
        """Limpia el gráfico de forma asíncrona."""
        self.data_points.clear()
        if self.chart:
            self.chart.data_series[0].data_points = []
            if len(self.chart.data_series) > 1:
                self.chart.data_series[1].data_points = []
        self._update_stats()
        if self.page:
            self.update()
            
    def _zoom_out(self, e):
        """Aumenta el rango Y del gráfico."""
        if self.chart:
            range_y = self.max_y - self.min_y
            self.min_y = max(0, self.min_y - range_y * 0.2)
            self.max_y = self.max_y + range_y * 0.2
            self.chart.min_y = self.min_y
            self.chart.max_y = self.max_y
            self.update()
            
    def _zoom_in(self, e):
        """Reduce el rango Y del gráfico."""
        if self.chart and self.data_points:
            latencies = [p.latency_ms for p in self.data_points]
            if latencies:
                self.min_y = max(0, min(latencies) - 5)
                self.max_y = max(latencies) + 10
                self.chart.min_y = self.min_y
                self.chart.max_y = self.max_y
                self.update()