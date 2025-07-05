"""Tests para asset discovery del firmware."""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from modules.bombercat_flash.firmware_manager import (
    FirmwareManager,
    AssetNotFoundError,
    FirmwareError
)


class TestAssetDiscovery:
    """Tests para descubrimiento de assets de firmware."""
    
    def setup_method(self):
        """Configuración para cada test."""
        self.manager = FirmwareManager("test/repo")
    
    def test_find_firmware_asset_success(self):
        """Test búsqueda exitosa de asset de firmware."""
        release_json = {
            "tag_name": "v1.0.0",
            "body": "SHA256 checksums:\nbombercat-esp32s2-v1.0.0.bin: a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
            "assets": [
                {
                    "name": "bombercat-esp32s2-v1.0.0.bin",
                    "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/bombercat-esp32s2-v1.0.0.bin"
                },
                {
                    "name": "other-file.txt",
                    "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/other-file.txt"
                }
            ]
        }
        
        result = self.manager._find_firmware_asset(release_json)
        
        assert result['name'] == "bombercat-esp32s2-v1.0.0.bin"
        assert result['sha256'] == "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
        assert "github.com" in result['download_url']
    
    def test_find_firmware_asset_no_bin_files(self):
        """Test cuando no hay archivos .bin."""
        release_json = {
            "tag_name": "v1.0.0",
            "body": "No binary files",
            "assets": [
                {
                    "name": "readme.txt",
                    "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/readme.txt"
                }
            ]
        }
        
        with pytest.raises(AssetNotFoundError, match="No se encontró asset de firmware ESP32-S2"):
            self.manager._find_firmware_asset(release_json)
    
    def test_find_firmware_asset_no_esp32s2(self):
        """Test cuando hay .bin pero no para ESP32-S2."""
        release_json = {
            "tag_name": "v1.0.0",
            "body": "SHA256 checksums:\nfirmware-esp32-v1.0.0.bin: a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
            "assets": [
                {
                    "name": "firmware-esp32-v1.0.0.bin",  # ESP32, no ESP32-S2
                    "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/firmware-esp32-v1.0.0.bin"
                }
            ]
        }
        
        with pytest.raises(AssetNotFoundError, match="No se encontró asset de firmware ESP32-S2"):
            self.manager._find_firmware_asset(release_json)
    
    def test_find_firmware_asset_no_checksum(self):
        """Test cuando no se encuentra checksum en el body."""
        release_json = {
            "tag_name": "v1.0.0",
            "body": "Release notes without checksums",
            "assets": [
                {
                    "name": "bombercat-esp32s2-v1.0.0.bin",
                    "browser_download_url": "https://github.com/test/repo/releases/download/v1.0.0/bombercat-esp32s2-v1.0.0.bin"
                }
            ]
        }
        
        with pytest.raises(AssetNotFoundError, match="No se encontró asset de firmware ESP32-S2"):
            self.manager._find_firmware_asset(release_json)
    
    def test_extract_sha256_from_body_success(self):
        """Test extracción exitosa de SHA256."""
        body = """Release v1.0.0
        
SHA256 checksums:
bombercat-esp32s2-v1.0.0.bin: A1B2C3D4E5F6789012345678901234567890123456789012345678901234567890
other-file.txt: 1234567890123456789012345678901234567890123456789012345678901234
        """
        
        result = self.manager._extract_sha256_from_body(body, "bombercat-esp32s2-v1.0.0.bin")
        
        assert result == "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
    
    def test_extract_sha256_from_body_different_format(self):
        """Test extracción con formato diferente."""
        body = "bombercat-esp32s2-v1.0.0.bin a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
        
        result = self.manager._extract_sha256_from_body(body, "bombercat-esp32s2-v1.0.0.bin")
        
        assert result == "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
    
    def test_extract_sha256_from_body_not_found(self):
        """Test cuando no se encuentra el SHA256."""
        body = "Release notes without checksums for the file"
        
        result = self.manager._extract_sha256_from_body(body, "bombercat-esp32s2-v1.0.0.bin")
        
        assert result is None
    
    def test_extract_sha256_from_body_invalid_hash(self):
        """Test con hash inválido (no 64 caracteres)."""
        body = "bombercat-esp32s2-v1.0.0.bin: invalidhash"
        
        result = self.manager._extract_sha256_from_body(body, "bombercat-esp32s2-v1.0.0.bin")
        
        assert result is None
    
    def test_extract_sha256_from_body_non_hex(self):
        """Test con caracteres no hexadecimales."""
        body = "bombercat-esp32s2-v1.0.0.bin: g1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
        
        result = self.manager._extract_sha256_from_body(body, "bombercat-esp32s2-v1.0.0.bin")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_latest_release_success(self):
        """Test obtención exitosa del último release."""
        mock_release_data = {
            "tag_name": "v1.0.0",
            "body": "Release notes",
            "assets": []
        }
        
        with patch('modules.bombercat_flash.firmware_manager.HttpClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = mock_release_data
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await self.manager.get_latest_release()
            
            assert result == mock_release_data
            mock_client.get.assert_called_once_with(
                "https://api.github.com/repos/test/repo/releases/latest"
            )
    
    @pytest.mark.asyncio
    async def test_get_latest_release_rate_limit_retry(self):
        """Test retry automático en caso de rate limit."""
        from modules.bombercat_flash.http_client import RateLimitError
        
        mock_release_data = {
            "tag_name": "v1.0.0",
            "body": "Release notes",
            "assets": []
        }
        
        with patch('modules.bombercat_flash.firmware_manager.HttpClient') as mock_client_class:
            with patch('asyncio.sleep') as mock_sleep:
                mock_client = AsyncMock()
                mock_response = Mock()
                mock_response.json.return_value = mock_release_data
                
                # Primera llamada falla con rate limit, segunda funciona
                mock_client.get.side_effect = [RateLimitError("Rate limit"), mock_response]
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                result = await self.manager.get_latest_release()
                
                assert result == mock_release_data
                mock_sleep.assert_called_once_with(60)  # Espera 60 segundos
                assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_list_available_versions_success(self):
        """Test listado exitoso de versiones disponibles."""
        mock_releases_data = [
            {"tag_name": "v1.2.0", "draft": False, "prerelease": False},
            {"tag_name": "v1.1.0", "draft": False, "prerelease": False},
            {"tag_name": "v1.0.0-beta", "draft": False, "prerelease": True},  # Excluir
            {"tag_name": "v0.9.0", "draft": True, "prerelease": False},  # Excluir
        ]
        
        with patch('modules.bombercat_flash.firmware_manager.HttpClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = mock_releases_data
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await self.manager.list_available_versions()
            
            assert result == ["v1.2.0", "v1.1.0"]
            mock_client.get.assert_called_once_with(
                "https://api.github.com/repos/test/repo/releases"
            )