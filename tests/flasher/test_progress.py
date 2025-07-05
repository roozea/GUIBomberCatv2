"""Tests para el sistema de progreso del flasher."""

import pytest
from unittest.mock import Mock, patch
from io import StringIO
import sys

from modules.bombercat_flash.progress import (
    ProgressPrinter,
    ProgressDelegate,
    CallbackProgressDelegate,
    SilentProgressDelegate,
    ProgressTracker
)


class TestProgressPrinter:
    """Tests para ProgressPrinter."""
    
    def test_progress_printer_initialization(self):
        """Test inicialización de ProgressPrinter."""
        printer = ProgressPrinter(description="Test Progress")
        assert printer.description == "Test Progress"
        assert printer.total == 100
        assert printer.pbar is None
    
    @patch('modules.bombercat_flash.progress.tqdm')
    def test_on_start(self, mock_tqdm):
        """Test método on_start."""
        mock_pbar = Mock()
        mock_tqdm.return_value = mock_pbar
        
        printer = ProgressPrinter()
        printer.on_start("Starting test")
        
        mock_tqdm.assert_called_once_with(
            total=100,
            desc="Flash Progress",
            unit="%",
            bar_format="{l_bar}{bar}| {n:.1f}/{total:.1f}% [{elapsed}<{remaining}]"
        )
        mock_pbar.set_description.assert_called_once_with("Starting test")
    
    def test_on_chunk(self):
        """Test método on_chunk."""
        printer = ProgressPrinter()
        mock_pbar = Mock()
        printer.pbar = mock_pbar
        
        printer.on_chunk(50.0, "Half way")
        
        mock_pbar.update.assert_called_once_with(50.0)
        mock_pbar.set_description.assert_called_once_with("Half way")
    
    def test_on_chunk_without_pbar(self):
        """Test on_chunk cuando no hay barra de progreso."""
        printer = ProgressPrinter()
        # No debería lanzar excepción
        printer.on_chunk(50.0, "Test")
    
    def test_on_end_success(self):
        """Test método on_end con éxito."""
        printer = ProgressPrinter()
        mock_pbar = Mock()
        printer.pbar = mock_pbar
        
        printer.on_end(True, "Completed successfully")
        
        mock_pbar.update.assert_called_once_with(100.0)
        mock_pbar.set_description.assert_called_once_with("✓ Completed successfully")
        mock_pbar.close.assert_called_once()
    
    def test_on_end_failure(self):
        """Test método on_end con fallo."""
        printer = ProgressPrinter()
        mock_pbar = Mock()
        printer.pbar = mock_pbar
        
        printer.on_end(False, "Failed")
        
        mock_pbar.set_description.assert_called_once_with("✗ Failed")
        mock_pbar.close.assert_called_once()


class TestCallbackProgressDelegate:
    """Tests para CallbackProgressDelegate."""
    
    def test_initialization(self):
        """Test inicialización con callbacks."""
        start_cb = Mock()
        chunk_cb = Mock()
        end_cb = Mock()
        
        delegate = CallbackProgressDelegate(
            on_start_callback=start_cb,
            on_chunk_callback=chunk_cb,
            on_end_callback=end_cb
        )
        
        assert delegate.on_start_callback == start_cb
        assert delegate.on_chunk_callback == chunk_cb
        assert delegate.on_end_callback == end_cb
    
    def test_on_start_with_callback(self):
        """Test on_start con callback."""
        callback = Mock()
        delegate = CallbackProgressDelegate(on_start_callback=callback)
        
        delegate.on_start("Starting")
        
        callback.assert_called_once_with("Starting")
    
    def test_on_start_without_callback(self):
        """Test on_start sin callback."""
        delegate = CallbackProgressDelegate()
        # No debería lanzar excepción
        delegate.on_start("Starting")
    
    def test_on_chunk_with_callback(self):
        """Test on_chunk con callback."""
        callback = Mock()
        delegate = CallbackProgressDelegate(on_chunk_callback=callback)
        
        delegate.on_chunk(75.0, "Progress")
        
        callback.assert_called_once_with(75.0, "Progress")
    
    def test_on_end_with_callback(self):
        """Test on_end con callback."""
        callback = Mock()
        delegate = CallbackProgressDelegate(on_end_callback=callback)
        
        delegate.on_end(True, "Done")
        
        callback.assert_called_once_with(True, "Done")


class TestSilentProgressDelegate:
    """Tests para SilentProgressDelegate."""
    
    def test_silent_operations(self):
        """Test que todas las operaciones son silenciosas."""
        delegate = SilentProgressDelegate()
        
        # Capturar stdout para verificar que no hay salida
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            delegate.on_start("Starting")
            delegate.on_chunk(50.0, "Progress")
            delegate.on_end(True, "Done")
            
            # Verificar que no hay salida
            output = captured_output.getvalue()
            assert output == ""
        finally:
            sys.stdout = old_stdout


class TestProgressTracker:
    """Tests para ProgressTracker."""
    
    def test_initialization(self):
        """Test inicialización de ProgressTracker."""
        tracker = ProgressTracker()
        assert tracker.delegates == []
    
    def test_add_delegate(self):
        """Test agregar delegate."""
        tracker = ProgressTracker()
        delegate = Mock(spec=ProgressDelegate)
        
        tracker.add_delegate(delegate)
        
        assert delegate in tracker.delegates
    
    def test_remove_delegate(self):
        """Test remover delegate."""
        tracker = ProgressTracker()
        delegate = Mock(spec=ProgressDelegate)
        
        tracker.add_delegate(delegate)
        tracker.remove_delegate(delegate)
        
        assert delegate not in tracker.delegates
    
    def test_on_start_multiple_delegates(self):
        """Test on_start con múltiples delegates."""
        tracker = ProgressTracker()
        delegate1 = Mock(spec=ProgressDelegate)
        delegate2 = Mock(spec=ProgressDelegate)
        
        tracker.add_delegate(delegate1)
        tracker.add_delegate(delegate2)
        
        tracker.on_start("Starting")
        
        delegate1.on_start.assert_called_once_with("Starting")
        delegate2.on_start.assert_called_once_with("Starting")
    
    def test_on_chunk_multiple_delegates(self):
        """Test on_chunk con múltiples delegates."""
        tracker = ProgressTracker()
        delegate1 = Mock(spec=ProgressDelegate)
        delegate2 = Mock(spec=ProgressDelegate)
        
        tracker.add_delegate(delegate1)
        tracker.add_delegate(delegate2)
        
        tracker.on_chunk(60.0, "Progress")
        
        delegate1.on_chunk.assert_called_once_with(60.0, "Progress")
        delegate2.on_chunk.assert_called_once_with(60.0, "Progress")
    
    def test_on_end_multiple_delegates(self):
        """Test on_end con múltiples delegates."""
        tracker = ProgressTracker()
        delegate1 = Mock(spec=ProgressDelegate)
        delegate2 = Mock(spec=ProgressDelegate)
        
        tracker.add_delegate(delegate1)
        tracker.add_delegate(delegate2)
        
        tracker.on_end(True, "Completed")
        
        delegate1.on_end.assert_called_once_with(True, "Completed")
        delegate2.on_end.assert_called_once_with(True, "Completed")
    
    def test_delegate_exception_handling(self):
        """Test manejo de excepciones en delegates."""
        tracker = ProgressTracker()
        
        # Delegate que lanza excepción
        failing_delegate = Mock(spec=ProgressDelegate)
        failing_delegate.on_start.side_effect = Exception("Test error")
        
        # Delegate normal
        normal_delegate = Mock(spec=ProgressDelegate)
        
        tracker.add_delegate(failing_delegate)
        tracker.add_delegate(normal_delegate)
        
        # No debería lanzar excepción, pero debería continuar con otros delegates
        tracker.on_start("Starting")
        
        failing_delegate.on_start.assert_called_once_with("Starting")
        normal_delegate.on_start.assert_called_once_with("Starting")


class TestProgressIntegration:
    """Tests de integración para el sistema de progreso."""
    
    @patch('modules.bombercat_flash.progress.tqdm')
    def test_full_progress_flow(self, mock_tqdm):
        """Test flujo completo de progreso."""
        mock_pbar = Mock()
        mock_tqdm.return_value = mock_pbar
        
        # Crear tracker con múltiples delegates
        tracker = ProgressTracker()
        printer = ProgressPrinter(description="Test Flash")
        callback_mock = Mock()
        callback_delegate = CallbackProgressDelegate(on_chunk_callback=callback_mock)
        
        tracker.add_delegate(printer)
        tracker.add_delegate(callback_delegate)
        
        # Simular flujo completo
        tracker.on_start("Iniciando flasheo")
        tracker.on_chunk(25.0, "Borrando flash")
        tracker.on_chunk(50.0, "Escribiendo firmware")
        tracker.on_chunk(75.0, "Verificando")
        tracker.on_end(True, "Flasheo completado")
        
        # Verificar llamadas a tqdm
        mock_tqdm.assert_called_once()
        assert mock_pbar.set_description.call_count == 5
        assert mock_pbar.update.call_count == 4
        mock_pbar.close.assert_called_once()
        
        # Verificar callback
        assert callback_mock.call_count == 3
        callback_mock.assert_any_call(25.0, "Borrando flash")
        callback_mock.assert_any_call(50.0, "Escribiendo firmware")
        callback_mock.assert_any_call(75.0, "Verificando")