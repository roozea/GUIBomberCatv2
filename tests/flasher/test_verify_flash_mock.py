"""Tests para verificación de firmware con mocks de esptool."""

import pytest
import tempfile
import zlib
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from modules.bombercat_flash.flasher import ESPFlasher
from modules.bombercat_flash.errors import ChecksumMismatch, FlashError


class TestVerifyFlashMocked:
    """Tests para verificación de firmware usando mocks."""
    
    def create_test_firmware(self, data: bytes) -> Path:
        """Crea un archivo de firmware de prueba.
        
        Args:
            data: Datos del firmware
            
        Returns:
            Path al archivo creado
        """
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
        tmp_file.write(data)
        tmp_file.flush()
        tmp_file.close()
        return Path(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_verify_flash_success(self):
        """Test verificación exitosa con CRC coincidente."""
        flasher = ESPFlasher()
        
        # Datos de prueba
        test_data = b'\xE9\x00\x00\x03' + b'\x00' * 4092  # 4096 bytes total
        firmware_path = self.create_test_firmware(test_data)
        
        try:
            # Mock de ESPLoader.detect_chip y métodos relacionados
            mock_esp = Mock()
            mock_esp.read_flash.return_value = test_data  # Mismos datos
            
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.return_value = mock_esp
                
                result = await flasher.verify_flash(
                    port="/dev/ttyUSB0",
                    firmware_path=firmware_path
                )
                
                assert result is True
                mock_loader.detect_chip.assert_called_once_with("/dev/ttyUSB0", flasher.baud_rate)
                mock_esp.connect.assert_called_once()
                mock_esp.read_flash.assert_called_once_with(0x1000, 4096)
                mock_esp.hard_reset.assert_called_once()
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_verify_flash_checksum_mismatch(self):
        """Test verificación con CRC no coincidente."""
        flasher = ESPFlasher()
        
        # Datos originales y datos diferentes en el dispositivo
        original_data = b'\xE9\x00\x00\x03' + b'\x00' * 4092
        device_data = b'\xE9\x00\x00\x03' + b'\xFF' * 4092  # Datos diferentes
        
        firmware_path = self.create_test_firmware(original_data)
        
        try:
            mock_esp = Mock()
            mock_esp.read_flash.return_value = device_data
            
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.return_value = mock_esp
                
                with pytest.raises(ChecksumMismatch) as exc_info:
                    await flasher.verify_flash(
                        port="/dev/ttyUSB0",
                        firmware_path=firmware_path
                    )
                
                assert "CRC mismatch" in str(exc_info.value)
                # Verificar que contiene los CRCs esperados
                original_crc = zlib.crc32(original_data) & 0xffffffff
                device_crc = zlib.crc32(device_data) & 0xffffffff
                assert f"original={original_crc:08x}" in str(exc_info.value)
                assert f"device={device_crc:08x}" in str(exc_info.value)
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_verify_flash_custom_read_size(self):
        """Test verificación con tamaño de lectura personalizado."""
        flasher = ESPFlasher()
        
        test_data = b'\xE9\x00\x00\x03' + b'\xAA' * 1020  # 1024 bytes total
        firmware_path = self.create_test_firmware(test_data)
        
        try:
            mock_esp = Mock()
            mock_esp.read_flash.return_value = test_data[:1024]  # Solo primeros 1024 bytes
            
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.return_value = mock_esp
                
                result = await flasher.verify_flash(
                    port="/dev/ttyUSB0",
                    firmware_path=firmware_path,
                    read_size=1024
                )
                
                assert result is True
                mock_esp.read_flash.assert_called_once_with(0x1000, 1024)
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_verify_flash_connection_error(self):
        """Test verificación con error de conexión."""
        flasher = ESPFlasher()
        
        test_data = b'\xE9\x00\x00\x03' + b'\x00' * 100
        firmware_path = self.create_test_firmware(test_data)
        
        try:
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.side_effect = Exception("Connection failed")
                
                with patch('modules.bombercat_flash.flasher.map_esptool_error') as mock_map:
                    mock_map.return_value = FlashError("Mapped connection error")
                    
                    with pytest.raises(FlashError) as exc_info:
                        await flasher.verify_flash(
                            port="/dev/ttyUSB0",
                            firmware_path=firmware_path
                        )
                    
                    assert "Mapped connection error" in str(exc_info.value)
                    mock_map.assert_called_once()
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_verify_flash_read_error(self):
        """Test verificación con error de lectura de flash."""
        flasher = ESPFlasher()
        
        test_data = b'\xE9\x00\x00\x03' + b'\x00' * 100
        firmware_path = self.create_test_firmware(test_data)
        
        try:
            mock_esp = Mock()
            mock_esp.read_flash.side_effect = Exception("Flash read error")
            
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.return_value = mock_esp
                
                with patch('modules.bombercat_flash.flasher.map_esptool_error') as mock_map:
                    mock_map.return_value = FlashError("Mapped read error")
                    
                    with pytest.raises(FlashError):
                        await flasher.verify_flash(
                            port="/dev/ttyUSB0",
                            firmware_path=firmware_path
                        )
                    
                    mock_esp.connect.assert_called_once()
                    mock_esp.read_flash.assert_called_once()
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_verify_flash_file_not_found(self):
        """Test verificación con archivo de firmware inexistente."""
        flasher = ESPFlasher()
        
        non_existent_path = Path("/path/that/does/not/exist.bin")
        
        with pytest.raises(FileNotFoundError):
            await flasher.verify_flash(
                port="/dev/ttyUSB0",
                firmware_path=non_existent_path
            )


class TestReadFlashDataMocked:
    """Tests para el método _read_flash_data con mocks."""
    
    def test_read_flash_data_success(self):
        """Test lectura exitosa de datos de flash."""
        flasher = ESPFlasher()
        
        expected_data = b'\xE9\x00\x00\x03' + b'\xAA' * 1020
        
        mock_esp = Mock()
        mock_esp.read_flash.return_value = expected_data
        
        with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
            mock_loader.detect_chip.return_value = mock_esp
            
            result = flasher._read_flash_data("/dev/ttyUSB0", 1024)
            
            assert result == expected_data
            mock_loader.detect_chip.assert_called_once_with("/dev/ttyUSB0", flasher.baud_rate)
            mock_esp.connect.assert_called_once()
            mock_esp.read_flash.assert_called_once_with(0x1000, 1024)
            mock_esp.hard_reset.assert_called_once()
    
    def test_read_flash_data_connection_error(self):
        """Test lectura con error de conexión."""
        flasher = ESPFlasher()
        
        with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
            mock_loader.detect_chip.side_effect = Exception("Connection failed")
            
            with patch('modules.bombercat_flash.flasher.map_esptool_error') as mock_map:
                mock_map.return_value = FlashError("Mapped error")
                
                with pytest.raises(FlashError):
                    flasher._read_flash_data("/dev/ttyUSB0", 1024)
                
                mock_map.assert_called_once()
    
    def test_read_flash_data_read_error(self):
        """Test lectura con error en read_flash."""
        flasher = ESPFlasher()
        
        mock_esp = Mock()
        mock_esp.read_flash.side_effect = Exception("Read failed")
        
        with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
            mock_loader.detect_chip.return_value = mock_esp
            
            with patch('modules.bombercat_flash.flasher.map_esptool_error') as mock_map:
                mock_map.return_value = FlashError("Read error")
                
                with pytest.raises(FlashError):
                    flasher._read_flash_data("/dev/ttyUSB0", 1024)
                
                mock_esp.connect.assert_called_once()
                mock_esp.read_flash.assert_called_once()


class TestCRCCalculation:
    """Tests para cálculo de CRC."""
    
    def test_crc_calculation_consistency(self):
        """Test que el cálculo de CRC es consistente."""
        test_data = b'\xE9\x00\x00\x03' + b'\x55' * 1020
        
        # Calcular CRC múltiples veces
        crc1 = zlib.crc32(test_data) & 0xffffffff
        crc2 = zlib.crc32(test_data) & 0xffffffff
        crc3 = zlib.crc32(test_data) & 0xffffffff
        
        assert crc1 == crc2 == crc3
    
    def test_crc_different_data(self):
        """Test que datos diferentes producen CRCs diferentes."""
        data1 = b'\xE9\x00\x00\x03' + b'\x00' * 1020
        data2 = b'\xE9\x00\x00\x03' + b'\xFF' * 1020
        
        crc1 = zlib.crc32(data1) & 0xffffffff
        crc2 = zlib.crc32(data2) & 0xffffffff
        
        assert crc1 != crc2
    
    def test_crc_empty_data(self):
        """Test CRC de datos vacíos."""
        empty_data = b''
        crc = zlib.crc32(empty_data) & 0xffffffff
        
        # CRC de datos vacíos debería ser 0
        assert crc == 0
    
    def test_crc_single_byte_changes(self):
        """Test que cambios de un solo byte afectan el CRC."""
        base_data = b'\xE9\x00\x00\x03' + b'\x00' * 1020
        
        # Cambiar un solo byte
        modified_data = bytearray(base_data)
        modified_data[100] = 0xFF
        modified_data = bytes(modified_data)
        
        crc_original = zlib.crc32(base_data) & 0xffffffff
        crc_modified = zlib.crc32(modified_data) & 0xffffffff
        
        assert crc_original != crc_modified


class TestVerifyFlashIntegration:
    """Tests de integración para verificación de firmware."""
    
    @pytest.mark.asyncio
    async def test_verify_flash_with_real_file_operations(self):
        """Test verificación con operaciones de archivo reales."""
        flasher = ESPFlasher()
        
        # Crear archivo de firmware real
        test_data = b'\xE9\x00\x00\x03' + b'\xAB' * 2044  # 2048 bytes
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp_file:
            tmp_file.write(test_data)
            tmp_file.flush()
            firmware_path = Path(tmp_file.name)
        
        try:
            # Mock solo la parte de comunicación con el dispositivo
            mock_esp = Mock()
            mock_esp.read_flash.return_value = test_data[:4096]  # Leer más de lo necesario
            
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.return_value = mock_esp
                
                result = await flasher.verify_flash(
                    port="/dev/ttyUSB0",
                    firmware_path=firmware_path,
                    read_size=2048
                )
                
                assert result is True
                mock_esp.read_flash.assert_called_once_with(0x1000, 2048)
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_verify_flash_partial_read(self):
        """Test verificación con lectura parcial del firmware."""
        flasher = ESPFlasher()
        
        # Crear firmware grande
        large_firmware = b'\xE9\x00\x00\x03' + b'\x12' * 10236  # 10240 bytes
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp_file:
            tmp_file.write(large_firmware)
            tmp_file.flush()
            firmware_path = Path(tmp_file.name)
        
        try:
            # Solo leer los primeros 1024 bytes
            mock_esp = Mock()
            mock_esp.read_flash.return_value = large_firmware[:1024]
            
            with patch('modules.bombercat_flash.flasher.ESPLoader') as mock_loader:
                mock_loader.detect_chip.return_value = mock_esp
                
                result = await flasher.verify_flash(
                    port="/dev/ttyUSB0",
                    firmware_path=firmware_path,
                    read_size=1024
                )
                
                assert result is True
                mock_esp.read_flash.assert_called_once_with(0x1000, 1024)
        finally:
            firmware_path.unlink()


@pytest.mark.hardware
class TestVerifyFlashHardware:
    """Tests que requieren hardware real (marcados para ejecución opcional)."""
    
    @pytest.mark.asyncio
    async def test_verify_flash_real_device(self):
        """Test verificación con dispositivo real (requiere hardware)."""
        # Este test solo se ejecuta si hay hardware disponible
        pytest.skip("Requiere hardware ESP32 conectado")
        
        flasher = ESPFlasher()
        
        # En un test real, usaríamos un puerto y firmware reales
        # result = await flasher.verify_flash(
        #     port="/dev/ttyUSB0",
        #     firmware_path="real_firmware.bin"
        # )
        # assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_flash_real_connection_failure(self):
        """Test verificación con fallo de conexión real."""
        pytest.skip("Requiere configuración específica de hardware")
        
        flasher = ESPFlasher()
        
        # Test con puerto que no existe o dispositivo desconectado
        # with pytest.raises(FlashError):
        #     await flasher.verify_flash(
        #         port="/dev/ttyUSB99",  # Puerto que no existe
        #         firmware_path="test_firmware.bin"
        #     )