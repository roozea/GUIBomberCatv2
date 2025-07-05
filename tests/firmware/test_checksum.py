"""Tests para verificación de checksum de firmware."""

import hashlib
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, Mock, AsyncMock

from modules.bombercat_flash.firmware_manager import (
    FirmwareManager,
    ChecksumError,
    FirmwareError
)


class TestChecksumVerification:
    """Tests para verificación de checksum."""
    
    def setup_method(self):
        """Configuración para cada test."""
        self.manager = FirmwareManager("test/repo")
    
    def test_verify_checksum_success(self):
        """Test verificación exitosa de checksum."""
        # Crear archivo temporal con contenido conocido
        test_content = b"Hello, BomberCat firmware!"
        expected_sha256 = hashlib.sha256(test_content).hexdigest()
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_path = Path(tmp_file.name)
        
        try:
            result = self.manager._verify_checksum(tmp_path, expected_sha256)
            assert result is True
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def test_verify_checksum_mismatch(self):
        """Test cuando el checksum no coincide."""
        test_content = b"Hello, BomberCat firmware!"
        wrong_sha256 = "0" * 64  # SHA256 incorrecto
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_path = Path(tmp_file.name)
        
        try:
            result = self.manager._verify_checksum(tmp_path, wrong_sha256)
            assert result is False
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def test_verify_checksum_file_not_exists(self):
        """Test cuando el archivo no existe."""
        non_existent_path = Path("/tmp/non_existent_file.bin")
        sha256 = "a" * 64
        
        result = self.manager._verify_checksum(non_existent_path, sha256)
        assert result is False
    
    def test_verify_checksum_case_insensitive(self):
        """Test que la verificación es insensible a mayúsculas/minúsculas."""
        test_content = b"Test content"
        expected_sha256_lower = hashlib.sha256(test_content).hexdigest().lower()
        expected_sha256_upper = expected_sha256_lower.upper()
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Ambos deben funcionar
            result_lower = self.manager._verify_checksum(tmp_path, expected_sha256_lower)
            result_upper = self.manager._verify_checksum(tmp_path, expected_sha256_upper)
            
            assert result_lower is True
            assert result_upper is True
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def test_verify_checksum_large_file(self):
        """Test verificación con archivo grande (chunks)."""
        # Crear archivo de ~20KB para probar lectura en chunks
        test_content = b"A" * 20480
        expected_sha256 = hashlib.sha256(test_content).hexdigest()
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_path = Path(tmp_file.name)
        
        try:
            result = self.manager._verify_checksum(tmp_path, expected_sha256)
            assert result is True
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def test_verify_checksum_io_error(self):
        """Test manejo de errores de I/O."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
        
        # Simular error de lectura
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            result = self.manager._verify_checksum(tmp_path, "a" * 64)
            assert result is False
        
        tmp_path.unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_download_firmware_checksum_success(self):
        """Test descarga completa con verificación exitosa."""
        test_content = b"Firmware binary content"
        expected_sha256 = hashlib.sha256(test_content).hexdigest()
        
        mock_release_data = {
            "tag_name": "v1.0.0",
            "body": f"bombercat-esp32s2-v1.0.0.bin: {expected_sha256}",
            "assets": [{
                "name": "bombercat-esp32s2-v1.0.0.bin",
                "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/bombercat-esp32s2-v1.0.0.bin"
            }]
        }
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir) / "firmware" / "bombercat-esp32s2-v1.0.0.bin"
            
            with patch.object(self.manager, 'get_latest_release') as mock_get_release:
                with patch.object(self.manager, '_download_with_progress') as mock_download:
                    mock_get_release.return_value = mock_release_data
                    
                    # Simular descarga escribiendo el archivo
                    async def mock_download_func(url, path, filename):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with open(path, 'wb') as f:
                            f.write(test_content)
                    
                    mock_download.side_effect = mock_download_func
                    
                    result_path = await self.manager.download_firmware(target_path=target_path)
                    
                    assert result_path == target_path
                    assert target_path.exists()
                    
                    # Verificar que el contenido es correcto
                    with open(target_path, 'rb') as f:
                        assert f.read() == test_content
    
    @pytest.mark.asyncio
    async def test_download_firmware_checksum_failure(self):
        """Test descarga con fallo de checksum."""
        test_content = b"Firmware binary content"
        wrong_sha256 = "0" * 64  # SHA256 incorrecto
        
        mock_release_data = {
            "tag_name": "v1.0.0",
            "body": f"bombercat-esp32s2-v1.0.0.bin: {wrong_sha256}",
            "assets": [{
                "name": "bombercat-esp32s2-v1.0.0.bin",
                "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/bombercat-esp32s2-v1.0.0.bin"
            }]
        }
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir) / "firmware" / "bombercat-esp32s2-v1.0.0.bin"
            
            with patch.object(self.manager, 'get_latest_release') as mock_get_release:
                with patch.object(self.manager, '_download_with_progress') as mock_download:
                    mock_get_release.return_value = mock_release_data
                    
                    # Simular descarga escribiendo el archivo
                    async def mock_download_func(url, path, filename):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with open(path, 'wb') as f:
                            f.write(test_content)
                    
                    mock_download.side_effect = mock_download_func
                    
                    with pytest.raises(ChecksumError, match="Checksum no coincide"):
                        await self.manager.download_firmware(target_path=target_path)
                    
                    # El archivo debe haber sido eliminado
                    assert not target_path.exists()
    
    @pytest.mark.asyncio
    async def test_download_with_progress_no_tqdm(self):
        """Test descarga sin tqdm (no disponible)."""
        test_content = b"Test firmware content"
        
        with patch('modules.bombercat_flash.firmware_manager.tqdm', None):
            with patch('modules.bombercat_flash.firmware_manager.HttpClient') as mock_client_class:
                mock_client = AsyncMock()
                
                # Mock para HEAD request (obtener tamaño)
                mock_head_response = Mock()
                mock_head_response.headers = {'content-length': str(len(test_content))}
                
                # Mock para streaming
                async def mock_stream(url):
                    yield test_content
                
                mock_client.get.return_value = mock_head_response
                mock_client.stream.return_value = mock_stream("test_url")
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                with tempfile.TemporaryDirectory() as tmp_dir:
                    target_path = Path(tmp_dir) / "test_firmware.bin"
                    
                    await self.manager._download_with_progress(
                        "https://example.com/firmware.bin",
                        target_path,
                        "test_firmware.bin"
                    )
                    
                    assert target_path.exists()
                    with open(target_path, 'rb') as f:
                        assert f.read() == test_content
    
    @pytest.mark.asyncio
    async def test_download_with_progress_with_tqdm(self):
        """Test descarga con barra de progreso tqdm."""
        test_content = b"Test firmware content"
        
        with patch('modules.bombercat_flash.firmware_manager.tqdm') as mock_tqdm_class:
            with patch('modules.bombercat_flash.firmware_manager.sys.stderr.isatty', return_value=True):
                with patch('modules.bombercat_flash.firmware_manager.HttpClient') as mock_client_class:
                    mock_tqdm = Mock()
                    mock_tqdm_class.return_value = mock_tqdm
                    
                    mock_client = AsyncMock()
                    
                    # Mock para HEAD request
                    mock_head_response = Mock()
                    mock_head_response.headers = {'content-length': str(len(test_content))}
                    
                    # Mock para streaming
                    async def mock_stream(url):
                        yield test_content
                    
                    mock_client.get.return_value = mock_head_response
                    mock_client.stream.return_value = mock_stream("test_url")
                    mock_client_class.return_value.__aenter__.return_value = mock_client
                    
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        target_path = Path(tmp_dir) / "test_firmware.bin"
                        
                        await self.manager._download_with_progress(
                            "https://example.com/firmware.bin",
                            target_path,
                            "test_firmware.bin"
                        )
                        
                        # Verificar que se creó la barra de progreso
                        mock_tqdm_class.assert_called_once()
                        mock_tqdm.update.assert_called_once_with(len(test_content))
                        mock_tqdm.close.assert_called_once()