"""Tests unitarios para la detección de chips del DeviceDetector."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from modules.bombercat_flash.detector import DeviceDetector


class TestDeviceDetectorChipDetection:
    """Tests para funcionalidad de detección de chips."""
    
    def setup_method(self):
        """Configuración para cada test."""
        self.detector = DeviceDetector()
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    def test_detect_chip_esp32s2_success(self, mock_detect_chip):
        """Test detección exitosa de chip ESP32-S2."""
        # Arrange
        mock_esp = Mock()
        mock_esp.CHIP_NAME = 'ESP32-S2'
        mock_detect_chip.return_value.__enter__ = Mock(return_value=mock_esp)
        mock_detect_chip.return_value.__exit__ = Mock(return_value=None)
        
        port = '/dev/ttyUSB0'
        
        # Act
        result = self.detector.detect_chip(port)
        
        # Assert
        assert result == 'esp32-s2'
        mock_detect_chip.assert_called_once_with(port)
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    def test_detect_chip_unsupported_chip(self, mock_detect_chip):
        """Test detección de chip no soportado."""
        # Arrange
        mock_esp = Mock()
        mock_esp.CHIP_NAME = 'ESP32-C3'  # Chip no soportado
        mock_detect_chip.return_value.__enter__ = Mock(return_value=mock_esp)
        mock_detect_chip.return_value.__exit__ = Mock(return_value=None)
        
        port = 'COM3'
        
        # Act
        result = self.detector.detect_chip(port)
        
        # Assert
        assert result is None
        mock_detect_chip.assert_called_once_with(port)
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    def test_detect_chip_connection_error(self, mock_detect_chip):
        """Test manejo de error de conexión."""
        # Arrange
        mock_detect_chip.side_effect = Exception("Failed to connect")
        
        port = '/dev/ttyUSB0'
        
        # Act
        result = self.detector.detect_chip(port)
        
        # Assert
        assert result is None
        mock_detect_chip.assert_called_once_with(port)
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    def test_detect_chip_serial_exception(self, mock_detect_chip):
        """Test manejo de excepción de puerto serie."""
        # Arrange
        mock_detect_chip.side_effect = OSError("Port not found")
        
        port = '/dev/nonexistent'
        
        # Act
        result = self.detector.detect_chip(port)
        
        # Assert
        assert result is None
        mock_detect_chip.assert_called_once_with(port)
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    def test_detect_chip_case_insensitive(self, mock_detect_chip):
        """Test que la detección sea insensible a mayúsculas/minúsculas."""
        # Arrange
        mock_esp = Mock()
        mock_esp.CHIP_NAME = 'ESP32-S2'  # Mayúsculas
        mock_detect_chip.return_value.__enter__ = Mock(return_value=mock_esp)
        mock_detect_chip.return_value.__exit__ = Mock(return_value=None)
        
        port = 'COM1'
        
        # Act
        result = self.detector.detect_chip(port)
        
        # Assert
        assert result == 'esp32-s2'  # Debe devolver en minúsculas
        mock_detect_chip.assert_called_once_with(port)
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_get_verified_devices_success(self, mock_comports, mock_detect_chip):
        """Test obtención de dispositivos verificados exitosamente."""
        # Arrange
        # Mock puerto detectado
        mock_port = Mock()
        mock_port.device = '/dev/ttyUSB0'
        mock_port.description = 'ESP32-S2 Dev Board'
        mock_port.hwid = 'USB VID:PID=303A:0002'
        mock_port.vid = 0x303A
        mock_port.pid = 0x0002
        mock_comports.return_value = [mock_port]
        
        # Mock detección de chip
        mock_esp = Mock()
        mock_esp.CHIP_NAME = 'ESP32-S2'
        mock_detect_chip.return_value.__enter__ = Mock(return_value=mock_esp)
        mock_detect_chip.return_value.__exit__ = Mock(return_value=None)
        
        # Act
        result = self.detector.get_verified_devices()
        
        # Assert
        assert len(result) == 1
        device = result[0]
        assert device['port'] == '/dev/ttyUSB0'
        assert device['description'] == 'ESP32-S2 Dev Board'
        assert device['hwid'] == 'USB VID:PID=303A:0002'
        assert device['chip_type'] == 'esp32-s2'
        
        mock_comports.assert_called_once()
        mock_detect_chip.assert_called_once_with('/dev/ttyUSB0')
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_get_verified_devices_chip_detection_fails(self, mock_comports, mock_detect_chip):
        """Test cuando la detección de chip falla para un dispositivo."""
        # Arrange
        mock_port = Mock()
        mock_port.device = '/dev/ttyUSB0'
        mock_port.description = 'ESP Device'
        mock_port.hwid = 'USB VID:PID=303A:0002'
        mock_port.vid = 0x303A
        mock_port.pid = 0x0002
        mock_comports.return_value = [mock_port]
        
        # Mock falla en detección de chip
        mock_detect_chip.side_effect = Exception("Connection failed")
        
        # Act
        result = self.detector.get_verified_devices()
        
        # Assert
        assert len(result) == 0  # No dispositivos verificados
        mock_comports.assert_called_once()
        mock_detect_chip.assert_called_once_with('/dev/ttyUSB0')
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_get_verified_devices_mixed_results(self, mock_comports, mock_detect_chip):
        """Test con múltiples dispositivos, algunos verificables y otros no."""
        # Arrange
        mock_port1 = Mock()
        mock_port1.device = '/dev/ttyUSB0'
        mock_port1.description = 'ESP32-S2'
        mock_port1.hwid = 'USB VID:PID=303A:0002'
        mock_port1.vid = 0x303A
        mock_port1.pid = 0x0002
        
        mock_port2 = Mock()
        mock_port2.device = '/dev/ttyUSB1'
        mock_port2.description = 'CP210x Bridge'
        mock_port2.hwid = 'USB VID:PID=10C4:EA60'
        mock_port2.vid = 0x10C4
        mock_port2.pid = 0xEA60
        
        mock_comports.return_value = [mock_port1, mock_port2]
        
        # Mock detección: primer puerto exitoso, segundo falla
        def mock_detect_side_effect(port):
            if port == '/dev/ttyUSB0':
                mock_esp = Mock()
                mock_esp.CHIP_NAME = 'ESP32-S2'
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=mock_esp)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context
            else:
                raise Exception("Not an ESP device")
        
        mock_detect_chip.side_effect = mock_detect_side_effect
        
        # Act
        result = self.detector.get_verified_devices()
        
        # Assert
        assert len(result) == 1
        assert result[0]['port'] == '/dev/ttyUSB0'
        assert result[0]['chip_type'] == 'esp32-s2'
        
        mock_comports.assert_called_once()
        assert mock_detect_chip.call_count == 2
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_get_verified_devices_no_potential_devices(self, mock_comports):
        """Test cuando no hay dispositivos potenciales detectados."""
        # Arrange
        mock_comports.return_value = []  # No hay puertos
        
        # Act
        result = self.detector.get_verified_devices()
        
        # Assert
        assert len(result) == 0
        mock_comports.assert_called_once()
    
    def test_supported_chips_contains_esp32s2(self):
        """Test que ESP32-S2 esté en la lista de chips soportados."""
        assert 'esp32-s2' in self.detector.supported_chips
    
    @patch('modules.bombercat_flash.detector.detect_chip')
    def test_detect_chip_with_different_supported_chips(self, mock_detect_chip):
        """Test detección con diferentes chips en la lista de soportados."""
        # Arrange
        # Modificar temporalmente la lista de chips soportados
        original_chips = self.detector.supported_chips.copy()
        self.detector.supported_chips = ['esp32-s2', 'esp32-c3']
        
        mock_esp = Mock()
        mock_esp.CHIP_NAME = 'ESP32-C3'
        mock_detect_chip.return_value.__enter__ = Mock(return_value=mock_esp)
        mock_detect_chip.return_value.__exit__ = Mock(return_value=None)
        
        port = '/dev/ttyUSB0'
        
        try:
            # Act
            result = self.detector.detect_chip(port)
            
            # Assert
            assert result == 'esp32-c3'
            mock_detect_chip.assert_called_once_with(port)
        finally:
            # Restaurar lista original
            self.detector.supported_chips = original_chips