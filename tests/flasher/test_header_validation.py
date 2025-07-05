"""Tests para la validación de cabeceras de firmware."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from modules.bombercat_flash.flasher import ESPFlasher
from modules.bombercat_flash.errors import InvalidFirmwareError


class TestFirmwareHeaderValidation:
    """Tests para validación de cabeceras de firmware ESP32."""
    
    def test_valid_esp32_header(self):
        """Test validación de cabecera ESP32 válida."""
        # Cabecera válida: magic byte 0xE9, multicore byte 0x03
        valid_header = bytes([0xE9, 0x00, 0x00, 0x03])
        
        result = ESPFlasher._validate_firmware_header(valid_header)
        
        assert result is True
    
    def test_invalid_magic_byte(self):
        """Test validación con magic byte inválido."""
        # Magic byte incorrecto (0xE8 en lugar de 0xE9)
        invalid_header = bytes([0xE8, 0x00, 0x00, 0x03])
        
        result = ESPFlasher._validate_firmware_header(invalid_header)
        
        assert result is False
    
    def test_invalid_multicore_byte_warning(self):
        """Test validación con byte multicore diferente (debería advertir pero no fallar)."""
        # Magic byte correcto, pero multicore byte diferente
        header_with_warning = bytes([0xE9, 0x00, 0x00, 0x02])
        
        with patch('modules.bombercat_flash.flasher.logger') as mock_logger:
            result = ESPFlasher._validate_firmware_header(header_with_warning)
            
            assert result is True  # No debería fallar
            mock_logger.warning.assert_called_once()
            assert "Byte multicore inesperado" in mock_logger.warning.call_args[0][0]
    
    def test_header_too_short(self):
        """Test validación con cabecera demasiado corta."""
        short_header = bytes([0xE9, 0x00])  # Solo 2 bytes
        
        result = ESPFlasher._validate_firmware_header(short_header)
        
        assert result is False
    
    def test_empty_header(self):
        """Test validación con cabecera vacía."""
        empty_header = bytes()
        
        result = ESPFlasher._validate_firmware_header(empty_header)
        
        assert result is False
    
    def test_header_constants(self):
        """Test que las constantes de cabecera están definidas correctamente."""
        assert ESPFlasher.ESP32_MAGIC_BYTE == 0xE9
        assert ESPFlasher.ESP32_MULTICORE_BYTE == 0x03


class TestAsyncHeaderValidation:
    """Tests para validación asíncrona de cabeceras."""
    
    @pytest.mark.asyncio
    async def test_validate_firmware_header_async_valid(self):
        """Test validación asíncrona con firmware válido."""
        flasher = ESPFlasher()
        
        # Crear archivo temporal con cabecera válida
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            valid_header = bytes([0xE9, 0x00, 0x00, 0x03])
            tmp_file.write(valid_header)
            tmp_file.write(b'\x00' * 100)  # Datos adicionales
            tmp_file.flush()
            
            try:
                result = await flasher._validate_firmware_header_async(Path(tmp_file.name))
                assert result is True
            finally:
                Path(tmp_file.name).unlink()  # Limpiar archivo temporal
    
    @pytest.mark.asyncio
    async def test_validate_firmware_header_async_invalid(self):
        """Test validación asíncrona con firmware inválido."""
        flasher = ESPFlasher()
        
        # Crear archivo temporal con cabecera inválida
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            invalid_header = bytes([0xE8, 0x00, 0x00, 0x03])  # Magic byte incorrecto
            tmp_file.write(invalid_header)
            tmp_file.flush()
            
            try:
                result = await flasher._validate_firmware_header_async(Path(tmp_file.name))
                assert result is False
            finally:
                Path(tmp_file.name).unlink()
    
    @pytest.mark.asyncio
    async def test_validate_firmware_header_async_file_not_found(self):
        """Test validación asíncrona con archivo inexistente."""
        flasher = ESPFlasher()
        
        non_existent_path = Path("/path/that/does/not/exist.bin")
        
        with patch('modules.bombercat_flash.flasher.logger') as mock_logger:
            result = await flasher._validate_firmware_header_async(non_existent_path)
            
            assert result is False
            mock_logger.error.assert_called_once()
            assert "Error validando cabecera" in mock_logger.error.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_validate_firmware_header_async_read_error(self):
        """Test validación asíncrona con error de lectura."""
        flasher = ESPFlasher()
        
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with patch('modules.bombercat_flash.flasher.logger') as mock_logger:
                result = await flasher._validate_firmware_header_async(Path("test.bin"))
                
                assert result is False
                mock_logger.error.assert_called_once()


class TestHeaderValidationIntegration:
    """Tests de integración para validación de cabeceras."""
    
    def create_test_firmware(self, header_bytes: bytes, size: int = 1024) -> Path:
        """Crea un archivo de firmware de prueba.
        
        Args:
            header_bytes: Bytes de cabecera
            size: Tamaño total del archivo
            
        Returns:
            Path al archivo creado
        """
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
        tmp_file.write(header_bytes)
        
        # Rellenar con datos adicionales
        remaining_size = size - len(header_bytes)
        if remaining_size > 0:
            tmp_file.write(b'\x00' * remaining_size)
        
        tmp_file.flush()
        tmp_file.close()
        
        return Path(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_flash_device_with_valid_header(self):
        """Test flasheo con cabecera válida."""
        flasher = ESPFlasher()
        
        # Crear firmware con cabecera válida
        valid_header = bytes([0xE9, 0x00, 0x00, 0x03])
        firmware_path = self.create_test_firmware(valid_header)
        
        try:
            with patch.object(flasher, '_flash_sync', return_value=True):
                with patch.object(flasher, 'verify_flash', return_value=True):
                    result = await flasher.flash_device(
                        port="/dev/ttyUSB0",
                        firmware_path=firmware_path,
                        verify=False  # Evitar verificación real
                    )
                    
                    assert result is True
        finally:
            firmware_path.unlink()  # Limpiar
    
    @pytest.mark.asyncio
    async def test_flash_device_with_invalid_header(self):
        """Test flasheo con cabecera inválida."""
        flasher = ESPFlasher()
        
        # Crear firmware con cabecera inválida
        invalid_header = bytes([0xE8, 0x00, 0x00, 0x03])  # Magic byte incorrecto
        firmware_path = self.create_test_firmware(invalid_header)
        
        try:
            with pytest.raises(InvalidFirmwareError) as exc_info:
                await flasher.flash_device(
                    port="/dev/ttyUSB0",
                    firmware_path=firmware_path
                )
            
            assert "Cabecera de firmware inválida" in str(exc_info.value)
        finally:
            firmware_path.unlink()
    
    @pytest.mark.asyncio
    async def test_flash_device_with_nonexistent_firmware(self):
        """Test flasheo con archivo de firmware inexistente."""
        flasher = ESPFlasher()
        
        with pytest.raises(InvalidFirmwareError) as exc_info:
            await flasher.flash_device(
                port="/dev/ttyUSB0",
                firmware_path="/path/that/does/not/exist.bin"
            )
        
        assert "Archivo de firmware no encontrado" in str(exc_info.value)


class TestRealWorldFirmwareHeaders:
    """Tests con ejemplos de cabeceras de firmware del mundo real."""
    
    def test_esp32_bootloader_header(self):
        """Test con cabecera típica de bootloader ESP32."""
        # Cabecera típica de bootloader ESP32
        bootloader_header = bytes([
            0xE9,  # Magic byte
            0x02,  # Segment count
            0x02,  # Flash mode (DIO)
            0x03,  # Flash size/freq
        ])
        
        result = ESPFlasher._validate_firmware_header(bootloader_header)
        assert result is True
    
    def test_esp32_app_header(self):
        """Test con cabecera típica de aplicación ESP32."""
        # Cabecera típica de aplicación ESP32
        app_header = bytes([
            0xE9,  # Magic byte
            0x04,  # Segment count
            0x02,  # Flash mode
            0x03,  # Flash size/freq
        ])
        
        result = ESPFlasher._validate_firmware_header(app_header)
        assert result is True
    
    def test_esp8266_header(self):
        """Test con cabecera de ESP8266 (diferente formato)."""
        # ESP8266 usa un formato ligeramente diferente
        esp8266_header = bytes([
            0xE9,  # Magic byte (mismo que ESP32)
            0x02,  # Segment count
            0x01,  # Flash mode
            0x02,  # Flash size/freq (diferente)
        ])
        
        # Debería pasar el magic byte pero advertir sobre multicore
        with patch('modules.bombercat_flash.flasher.logger') as mock_logger:
            result = ESPFlasher._validate_firmware_header(esp8266_header)
            
            assert result is True
            mock_logger.warning.assert_called_once()
    
    def test_corrupted_firmware_header(self):
        """Test con cabecera corrupta."""
        corrupted_headers = [
            bytes([0x00, 0x00, 0x00, 0x00]),  # Todo ceros
            bytes([0xFF, 0xFF, 0xFF, 0xFF]),  # Todo unos
            bytes([0xAA, 0x55, 0xAA, 0x55]),  # Patrón alternante
            bytes([0xDE, 0xAD, 0xBE, 0xEF]),  # Datos aleatorios
        ]
        
        for header in corrupted_headers:
            result = ESPFlasher._validate_firmware_header(header)
            assert result is False, f"Header corrupta debería fallar: {header.hex()}"


class TestHeaderValidationPerformance:
    """Tests de rendimiento para validación de cabeceras."""
    
    def test_header_validation_speed(self):
        """Test que la validación de cabecera es rápida."""
        import time
        
        header = bytes([0xE9, 0x00, 0x00, 0x03])
        
        start_time = time.time()
        
        # Ejecutar validación muchas veces
        for _ in range(10000):
            ESPFlasher._validate_firmware_header(header)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Debería ser muy rápido (menos de 1 segundo para 10k validaciones)
        assert elapsed < 1.0, f"Validación demasiado lenta: {elapsed:.3f}s"
    
    @pytest.mark.asyncio
    async def test_async_header_validation_speed(self):
        """Test que la validación asíncrona no es significativamente más lenta."""
        import time
        
        flasher = ESPFlasher()
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            header = bytes([0xE9, 0x00, 0x00, 0x03])
            tmp_file.write(header)
            tmp_file.write(b'\x00' * 100)
            tmp_file.flush()
            
            try:
                start_time = time.time()
                
                # Ejecutar validación asíncrona varias veces
                for _ in range(100):
                    await flasher._validate_firmware_header_async(Path(tmp_file.name))
                
                end_time = time.time()
                elapsed = end_time - start_time
                
                # Debería ser razonablemente rápido
                assert elapsed < 5.0, f"Validación asíncrona demasiado lenta: {elapsed:.3f}s"
            finally:
                Path(tmp_file.name).unlink()