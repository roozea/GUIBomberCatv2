#!/usr/bin/env python3
"""
Dashboard simple para probar Flet
"""

import flet as ft
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def simple_dashboard(page: ft.Page):
    """Dashboard simple para probar."""
    logger.info("Iniciando dashboard simple...")
    
    page.title = "Test Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    
    # Crear contenido simple
    title = ft.Text("🚀 Dashboard Funcionando", size=24, weight=ft.FontWeight.BOLD)
    subtitle = ft.Text("El dashboard está corriendo correctamente", size=16)
    status = ft.Text("✅ Estado: Activo", color=ft.colors.GREEN)
    
    # Contenedor principal
    main_container = ft.Container(
        content=ft.Column([
            title,
            subtitle,
            status,
            ft.ElevatedButton("Test Button", on_click=lambda e: logger.info("Button clicked"))
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.alignment.center,
        expand=True,
        padding=20
    )
    
    page.add(main_container)
    logger.info("Dashboard simple inicializado")

def main():
    """Función principal."""
    try:
        ft.app(
            target=simple_dashboard,
            name="test-dashboard",
            port=8551,
            view=ft.AppView.WEB_BROWSER,
            web_renderer=ft.WebRenderer.HTML,
        )
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()