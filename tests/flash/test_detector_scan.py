"""Tests unitarios para el escaneo de puertos del DeviceDetector."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from modules.bombercat_flash.detector import DeviceDetector


class TestDeviceDetectorScan:
    """Tests para funcionalidad de escaneo de puertos."""
    
    def setup_method(self):
        """Configuración para cada test."""
        self.detector = DeviceDetector()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_empty_list(self, mock_comports):
        """Test escaneo cuando no hay puertos disponibles."""
        # Arrange
        mock_comports.return_value = []
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert result == []
        mock_comports.assert_called_once()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_no_esp_devices(self, mock_comports):
        """Test escaneo cuando hay puertos pero ninguno es ESP."""
        # Arrange
        mock_port = Mock()
        mock_port.device = '/dev/ttyUSB0'
        mock_port.description = 'Generic USB Serial'
        mock_port.hwid = 'USB VID:PID=1234:5678'
        mock_port.vid = 0x1234
        mock_port.pid = 0x5678
        
        mock_comports.return_value = [mock_port]
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert result == []
        mock_comports.assert_called_once()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_esp32s2_by_vid_pid(self, mock_comports):
        """Test detección de ESP32-S2 por VID/PID."""
        # Arrange
        mock_port = Mock()
        mock_port.device = '/dev/ttyUSB0'
        mock_port.description = 'ESP32-S2 Dev Board'
        mock_port.hwid = 'USB VID:PID=303A:0002'
        mock_port.vid = 0x303A  # Espressif VID
        mock_port.pid = 0x0002  # ESP32-S2 PID
        
        mock_comports.return_value = [mock_port]
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert len(result) == 1
        assert result[0]['port'] == '/dev/ttyUSB0'
        assert result[0]['description'] == 'ESP32-S2 Dev Board'
        assert result[0]['hwid'] == 'USB VID:PID=303A:0002'
        mock_comports.assert_called_once()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_cp210x_device(self, mock_comports):
        """Test detección de dispositivo con chip CP210x."""
        # Arrange
        mock_port = Mock()
        mock_port.device = 'COM3'
        mock_port.description = 'Silicon Labs CP210x USB to UART Bridge'
        mock_port.hwid = 'USB VID:PID=10C4:EA60'
        mock_port.vid = 0x10C4  # Silicon Labs VID
        mock_port.pid = 0xEA60  # CP210x PID
        
        mock_comports.return_value = [mock_port]
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert len(result) == 1
        assert result[0]['port'] == 'COM3'
        assert 'Silicon Labs' in result[0]['description']
        mock_comports.assert_called_once()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_multiple_devices(self, mock_comports):
        """Test escaneo con múltiples dispositivos ESP."""
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
        
        mock_port3 = Mock()  # Puerto no-ESP
        mock_port3.device = '/dev/ttyUSB2'
        mock_port3.description = 'Generic Serial'
        mock_port3.hwid = 'USB VID:PID=1234:5678'
        mock_port3.vid = 0x1234
        mock_port3.pid = 0x5678
        
        mock_comports.return_value = [mock_port1, mock_port2, mock_port3]
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert len(result) == 2
        ports = [device['port'] for device in result]
        assert '/dev/ttyUSB0' in ports
        assert '/dev/ttyUSB1' in ports
        assert '/dev/ttyUSB2' not in ports
        mock_comports.assert_called_once()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_description_fallback(self, mock_comports):
        """Test detección por descripción cuando VID/PID no están disponibles."""
        # Arrange
        mock_port = Mock()
        mock_port.device = '/dev/ttyACM0'
        mock_port.description = 'ESP Development Board'
        mock_port.hwid = 'Unknown'
        mock_port.vid = None
        mock_port.pid = None
        
        mock_comports.return_value = [mock_port]
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert len(result) == 1
        assert result[0]['port'] == '/dev/ttyACM0'
        assert 'ESP Development Board' in result[0]['description']
        mock_comports.assert_called_once()
    
    @patch('modules.bombercat_flash.detector.serial.tools.list_ports.comports')
    def test_scan_ports_missing_attributes(self, mock_comports):
        """Test manejo de puertos con atributos faltantes."""
        # Arrange
        mock_port = Mock()
        mock_port.device = 'COM1'
        mock_port.description = None
        mock_port.hwid = None
        mock_port.vid = 0x303A
        mock_port.pid = 0x0002
        
        mock_comports.return_value = [mock_port]
        
        # Act
        result = self.detector.scan_ports()
        
        # Assert
        assert len(result) == 1
        assert result[0]['port'] == 'COM1'
        assert result[0]['description'] == 'Unknown'
        assert result[0]['hwid'] == 'Unknown'
        mock_comports.assert_called_once()
    
    def test_is_esp_device_by_vid_pid(self):
        """Test detección de dispositivo ESP por VID/PID."""
        # Arrange
        mock_port = Mock()
        mock_port.vid = 0x303A
        mock_port.pid = 0x0002
        mock_port.description = 'Some device'
        
        # Act
        result = self.detector._is_esp_device(mock_port)
        
        # Assert
        assert result is True
    
    def test_is_esp_device_by_description(self):
        """Test detección de dispositivo ESP por descripción."""
        # Arrange
        mock_port = Mock()
        mock_port.vid = None
        mock_port.pid = None
        mock_port.description = 'Silicon Labs CP210x USB Bridge'
        
        # Act
        result = self.detector._is_esp_device(mock_port)
        
        # Assert
        assert result is True
    
    def test_is_esp_device_not_esp(self):
        """Test que dispositivo no-ESP no sea detectado."""
        # Arrange
        mock_port = Mock()
        mock_port.vid = 0x1234
        mock_port.pid = 0x5678
        mock_port.description = 'Generic USB Serial Device'
        
        # Act
        result = self.detector._is_esp_device(mock_port)
        
        # Assert
        assert result is False
    
    def test_supported_chips_attribute(self):
        """Test que el atributo supported_chips esté configurado correctamente."""
        assert hasattr(self.detector, 'supported_chips')
        assert isinstance(self.detector.supported_chips, list)
        assert 'esp32-s2' in self.detector.supported_chips