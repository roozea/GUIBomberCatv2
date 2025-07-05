"""Módulo de progreso para el Flash Wizard.

Este módulo proporciona clases para manejar el progreso durante el flasheo
de firmware, incluyendo barras de progreso CLI y callbacks personalizados.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from tqdm import tqdm


class ProgressDelegate(ABC):
    """Interface abstracta para delegados de progreso.
    
    Permite implementar diferentes tipos de reportes de progreso
    (CLI, GUI, logging, etc.) de manera uniforme.
    """
    
    @abstractmethod
    def on_start(self, total_size: int, operation: str = "Flashing") -> None:
        """Llamado al inicio de la operación.
        
        Args:
            total_size: Tamaño total en bytes
            operation: Descripción de la operación
        """
        pass
    
    @abstractmethod
    def on_chunk(self, chunk_size: int, current_progress: int) -> None:
        """Llamado por cada chunk procesado.
        
        Args:
            chunk_size: Tamaño del chunk actual en bytes
            current_progress: Progreso acumulado en bytes
        """
        pass
    
    @abstractmethod
    def on_end(self, success: bool, message: str = "") -> None:
        """Llamado al finalizar la operación.
        
        Args:
            success: True si la operación fue exitosa
            message: Mensaje adicional (error o éxito)
        """
        pass


class ProgressPrinter(ProgressDelegate):
    """Implementación de progreso para CLI usando tqdm.
    
    Muestra una barra de progreso elegante en la terminal
    con información de velocidad y tiempo estimado.
    """
    
    def __init__(self, show_speed: bool = True, unit: str = "B"):
        """Inicializa el printer de progreso.
        
        Args:
            show_speed: Si mostrar velocidad de transferencia
            unit: Unidad para mostrar (B, KB, MB)
        """
        self.show_speed = show_speed
        self.unit = unit
        self.progress_bar: Optional[tqdm] = None
        self.start_time: Optional[float] = None
        
    def on_start(self, total_size: int, operation: str = "Flashing") -> None:
        """Inicia la barra de progreso."""
        self.start_time = time.time()
        
        # Configurar unidades apropiadas
        unit_scale = True
        if self.unit.upper() == "KB":
            total_size = total_size // 1024
            unit_scale = False
        elif self.unit.upper() == "MB":
            total_size = total_size // (1024 * 1024)
            unit_scale = False
            
        self.progress_bar = tqdm(
            total=total_size,
            desc=f"🔥 {operation}",
            unit=self.unit,
            unit_scale=unit_scale,
            unit_divisor=1024,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            colour="green",
            dynamic_ncols=True
        )
        
    def on_chunk(self, chunk_size: int, current_progress: int) -> None:
        """Actualiza la barra de progreso."""
        if self.progress_bar:
            # Ajustar chunk_size según la unidad
            display_chunk = chunk_size
            if self.unit.upper() == "KB":
                display_chunk = chunk_size // 1024
            elif self.unit.upper() == "MB":
                display_chunk = chunk_size // (1024 * 1024)
                
            self.progress_bar.update(display_chunk)
            
    def on_end(self, success: bool, message: str = "") -> None:
        """Finaliza la barra de progreso."""
        if self.progress_bar:
            if success:
                self.progress_bar.set_description("✅ Completado")
                self.progress_bar.colour = "green"
            else:
                self.progress_bar.set_description("❌ Error")
                self.progress_bar.colour = "red"
                
            self.progress_bar.close()
            
        # Mostrar mensaje final
        if message:
            status_icon = "✅" if success else "❌"
            print(f"{status_icon} {message}")
            
        # Mostrar tiempo total
        if self.start_time:
            elapsed = time.time() - self.start_time
            print(f"⏱️  Tiempo total: {elapsed:.2f}s")


class CallbackProgressDelegate(ProgressDelegate):
    """Delegado que ejecuta callbacks personalizados.
    
    Útil para integrar con interfaces gráficas o sistemas
    de logging personalizados.
    """
    
    def __init__(
        self,
        on_start_callback: Optional[Callable[[int, str], None]] = None,
        on_chunk_callback: Optional[Callable[[int, int], None]] = None,
        on_end_callback: Optional[Callable[[bool, str], None]] = None
    ):
        """Inicializa con callbacks opcionales.
        
        Args:
            on_start_callback: Función llamada al inicio
            on_chunk_callback: Función llamada por cada chunk
            on_end_callback: Función llamada al final
        """
        self._on_start_callback = on_start_callback
        self._on_chunk_callback = on_chunk_callback
        self._on_end_callback = on_end_callback
        
    def on_start(self, total_size: int, operation: str = "Flashing") -> None:
        """Ejecuta callback de inicio si está definido."""
        if self._on_start_callback:
            self._on_start_callback(total_size, operation)
            
    def on_chunk(self, chunk_size: int, current_progress: int) -> None:
        """Ejecuta callback de chunk si está definido."""
        if self._on_chunk_callback:
            self._on_chunk_callback(chunk_size, current_progress)
            
    def on_end(self, success: bool, message: str = "") -> None:
        """Ejecuta callback de fin si está definido."""
        if self._on_end_callback:
            self._on_end_callback(success, message)


class SilentProgressDelegate(ProgressDelegate):
    """Delegado silencioso que no muestra progreso.
    
    Útil para operaciones en background o cuando no se
    desea mostrar progreso visual.
    """
    
    def on_start(self, total_size: int, operation: str = "Flashing") -> None:
        """No hace nada."""
        pass
        
    def on_chunk(self, chunk_size: int, current_progress: int) -> None:
        """No hace nada."""
        pass
        
    def on_end(self, success: bool, message: str = "") -> None:
        """No hace nada."""
        pass


class ProgressTracker:
    """Tracker de progreso que coordina múltiples delegados.
    
    Permite usar múltiples tipos de progreso simultáneamente
    (ej: CLI + logging + GUI).
    """
    
    def __init__(self, delegates: list[ProgressDelegate]):
        """Inicializa con lista de delegados.
        
        Args:
            delegates: Lista de delegados de progreso
        """
        self.delegates = delegates
        self.total_size = 0
        self.current_progress = 0
        
    def start(self, total_size: int, operation: str = "Flashing") -> None:
        """Inicia el tracking en todos los delegados."""
        self.total_size = total_size
        self.current_progress = 0
        
        for delegate in self.delegates:
            try:
                delegate.on_start(total_size, operation)
            except Exception as e:
                # No fallar si un delegado tiene problemas
                print(f"Warning: Progress delegate error on start: {e}")
                
    def update(self, chunk_size: int) -> None:
        """Actualiza el progreso en todos los delegados."""
        self.current_progress += chunk_size
        
        for delegate in self.delegates:
            try:
                delegate.on_chunk(chunk_size, self.current_progress)
            except Exception as e:
                print(f"Warning: Progress delegate error on update: {e}")
                
    def finish(self, success: bool, message: str = "") -> None:
        """Finaliza el tracking en todos los delegados."""
        for delegate in self.delegates:
            try:
                delegate.on_end(success, message)
            except Exception as e:
                print(f"Warning: Progress delegate error on finish: {e}")
                
    @property
    def progress_percentage(self) -> float:
        """Retorna el porcentaje de progreso actual."""
        if self.total_size == 0:
            return 0.0
        return (self.current_progress / self.total_size) * 100.0
        
    @property
    def is_complete(self) -> bool:
        """Retorna True si el progreso está completo."""
        return self.current_progress >= self.total_size