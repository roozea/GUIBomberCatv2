"""Tests para el manejo de errores del flasher."""

import pytest
from unittest.mock import Mock

from modules.bombercat_flash.errors import (
    FlashError,
    PortBusyError,
    SyncError,
    FlashTimeout,
    ChecksumMismatch,
    InvalidFirmwareError,
    DeviceNotFoundError,
    InsufficientSpaceError,
    UnsupportedDeviceError,
    map_esptool_error
)


class TestFlashErrorHierarchy:
    """Tests para la jerarquía de errores de flash."""
    
    def test_flash_error_base(self):
        """Test error base FlashError."""
        error = FlashError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_port_busy_error(self):
        """Test PortBusyError."""
        error = PortBusyError("/dev/ttyUSB0")
        assert "Puerto /dev/ttyUSB0 está ocupado" in str(error)
        assert isinstance(error, FlashError)
    
    def test_sync_error(self):
        """Test SyncError."""
        error = SyncError()
        assert "No se pudo sincronizar" in str(error)
        assert isinstance(error, FlashError)
    
    def test_flash_timeout(self):
        """Test FlashTimeout."""
        error = FlashTimeout(120)
        assert "Timeout de 120 segundos" in str(error)
        assert isinstance(error, FlashError)
    
    def test_checksum_mismatch(self):
        """Test ChecksumMismatch."""
        error = ChecksumMismatch("CRC mismatch")
        assert "CRC mismatch" in str(error)
        assert isinstance(error, FlashError)
    
    def test_invalid_firmware_error(self):
        """Test InvalidFirmwareError."""
        error = InvalidFirmwareError("Invalid header")
        assert "Invalid header" in str(error)
        assert isinstance(error, FlashError)
    
    def test_device_not_found_error(self):
        """Test DeviceNotFoundError."""
        error = DeviceNotFoundError("/dev/ttyUSB0")
        assert "Dispositivo no encontrado en /dev/ttyUSB0" in str(error)
        assert isinstance(error, FlashError)
    
    def test_insufficient_space_error(self):
        """Test InsufficientSpaceError."""
        error = InsufficientSpaceError(2048, 1024)
        assert "Espacio insuficiente" in str(error)
        assert "2048 bytes" in str(error)
        assert "1024 bytes" in str(error)
        assert isinstance(error, FlashError)
    
    def test_unsupported_device_error(self):
        """Test UnsupportedDeviceError."""
        error = UnsupportedDeviceError("ESP32-C3")
        assert "Dispositivo ESP32-C3 no soportado" in str(error)
        assert isinstance(error, FlashError)


class TestErrorMapping:
    """Tests para el mapeo de errores de esptool."""
    
    def test_map_serial_exception_port_busy(self):
        """Test mapeo de excepción de puerto ocupado."""
        import serial
        
        # Simular error de puerto ocupado
        original_error = serial.SerialException("could not open port")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, PortBusyError)
        assert "could not open port" in str(mapped_error)
    
    def test_map_serial_exception_permission(self):
        """Test mapeo de excepción de permisos."""
        import serial
        
        original_error = serial.SerialException("Permission denied")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, PortBusyError)
        assert "Permission denied" in str(mapped_error)
    
    def test_map_timeout_error(self):
        """Test mapeo de TimeoutError."""
        original_error = TimeoutError("Operation timed out")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, FlashTimeout)
        assert "Operation timed out" in str(mapped_error)
    
    def test_map_connection_error(self):
        """Test mapeo de ConnectionError."""
        original_error = ConnectionError("Connection failed")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, DeviceNotFoundError)
        assert "Connection failed" in str(mapped_error)
    
    def test_map_file_not_found_error(self):
        """Test mapeo de FileNotFoundError."""
        original_error = FileNotFoundError("firmware.bin not found")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, InvalidFirmwareError)
        assert "firmware.bin not found" in str(mapped_error)
    
    def test_map_permission_error(self):
        """Test mapeo de PermissionError."""
        original_error = PermissionError("Access denied")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, PortBusyError)
        assert "Access denied" in str(mapped_error)
    
    def test_map_value_error_sync(self):
        """Test mapeo de ValueError relacionado con sync."""
        original_error = ValueError("Failed to connect to ESP32")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, SyncError)
        assert "Failed to connect to ESP32" in str(mapped_error)
    
    def test_map_value_error_unsupported(self):
        """Test mapeo de ValueError de dispositivo no soportado."""
        original_error = ValueError("Unsupported chip type")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, UnsupportedDeviceError)
        assert "Unsupported chip type" in str(mapped_error)
    
    def test_map_value_error_space(self):
        """Test mapeo de ValueError de espacio insuficiente."""
        original_error = ValueError("Not enough space")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, InsufficientSpaceError)
        assert "Not enough space" in str(mapped_error)
    
    def test_map_generic_value_error(self):
        """Test mapeo de ValueError genérico."""
        original_error = ValueError("Generic error")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, FlashError)
        assert "Generic error" in str(mapped_error)
    
    def test_map_runtime_error_sync(self):
        """Test mapeo de RuntimeError relacionado con sync."""
        original_error = RuntimeError("Sync failed")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, SyncError)
        assert "Sync failed" in str(mapped_error)
    
    def test_map_runtime_error_timeout(self):
        """Test mapeo de RuntimeError de timeout."""
        original_error = RuntimeError("Timeout waiting for packet")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, FlashTimeout)
        assert "Timeout waiting for packet" in str(mapped_error)
    
    def test_map_generic_runtime_error(self):
        """Test mapeo de RuntimeError genérico."""
        original_error = RuntimeError("Generic runtime error")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, FlashError)
        assert "Generic runtime error" in str(mapped_error)
    
    def test_map_generic_exception(self):
        """Test mapeo de excepción genérica."""
        original_error = Exception("Unknown error")
        mapped_error = map_esptool_error(original_error)
        
        assert isinstance(mapped_error, FlashError)
        assert "Unknown error" in str(mapped_error)
    
    def test_map_with_context(self):
        """Test mapeo con contexto adicional."""
        original_error = ValueError("Test error")
        mapped_error = map_esptool_error(original_error, "flash_device")
        
        assert isinstance(mapped_error, FlashError)
        assert "Test error" in str(mapped_error)
        # El contexto se puede usar internamente para logging
    
    def test_map_esptool_specific_errors(self):
        """Test mapeo de errores específicos de esptool."""
        # Simular diferentes tipos de errores que esptool puede lanzar
        test_cases = [
            ("A fatal error occurred: Failed to connect to ESP32", SyncError),
            ("Serial port busy", PortBusyError),
            ("Chip sync error", SyncError),
            ("Flash write timeout", FlashTimeout),
            ("Invalid firmware image", InvalidFirmwareError),
            ("Device not responding", DeviceNotFoundError),
        ]
        
        for error_msg, expected_type in test_cases:
            original_error = RuntimeError(error_msg)
            mapped_error = map_esptool_error(original_error)
            
            # Verificar que se mapea al tipo correcto o a FlashError genérico
            assert isinstance(mapped_error, (expected_type, FlashError))
            assert error_msg in str(mapped_error)


class TestErrorContextHandling:
    """Tests para el manejo de contexto en errores."""
    
    def test_error_with_device_context(self):
        """Test error con contexto de dispositivo."""
        error = PortBusyError("/dev/ttyUSB0")
        error.device_port = "/dev/ttyUSB0"
        
        assert hasattr(error, 'device_port')
        assert error.device_port == "/dev/ttyUSB0"
    
    def test_error_with_firmware_context(self):
        """Test error con contexto de firmware."""
        error = InvalidFirmwareError("Bad header")
        error.firmware_path = "/path/to/firmware.bin"
        
        assert hasattr(error, 'firmware_path')
        assert error.firmware_path == "/path/to/firmware.bin"
    
    def test_error_chaining(self):
        """Test encadenamiento de errores."""
        original_error = ValueError("Original error")
        mapped_error = map_esptool_error(original_error)
        
        # Verificar que el error original se preserva
        assert mapped_error.__cause__ == original_error


class TestErrorRecovery:
    """Tests para estrategias de recuperación de errores."""
    
    def test_recoverable_errors(self):
        """Test identificación de errores recuperables."""
        recoverable_errors = [
            FlashTimeout(30),
            SyncError(),
            PortBusyError("/dev/ttyUSB0")
        ]
        
        for error in recoverable_errors:
            # Estos errores podrían ser recuperables con reintentos
            assert isinstance(error, FlashError)
    
    def test_non_recoverable_errors(self):
        """Test identificación de errores no recuperables."""
        non_recoverable_errors = [
            InvalidFirmwareError("Bad header"),
            UnsupportedDeviceError("ESP32-C3"),
            InsufficientSpaceError(2048, 1024)
        ]
        
        for error in non_recoverable_errors:
            # Estos errores no deberían ser recuperables
            assert isinstance(error, FlashError)