"""Tests para validación de configuración BomberCat.

Este módulo contiene pruebas unitarias para los validadores
de configuración incluyendo casos límite y errores.
"""

import pytest
from pydantic import ValidationError

from modules.bombercat_config.validators import (
    ConfigValidator, BomberCatConfig,
    validate_mode, validate_wifi_ssid, validate_wifi_password, validate_encryption_key
)


class TestBomberCatConfig:
    """Tests para el modelo BomberCatConfig."""
    
    def test_valid_config(self):
        """Test configuración válida completa."""
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        config = BomberCatConfig(**config_data)
        
        assert config.mode == "client"
        assert config.wifi_ssid == "TestNetwork"
        assert config.wifi_password == "password123"
        assert config.encryption_key == "0123456789ABCDEF0123456789ABCDEF"
    
    def test_mode_validation(self):
        """Test validación de modo."""
        # Modo válido client
        config = BomberCatConfig(
            mode="client",
            wifi_ssid="Test",
            wifi_password="password123",
            encryption_key="0123456789ABCDEF0123456789ABCDEF"
        )
        assert config.mode == "client"
        
        # Modo válido host
        config = BomberCatConfig(
            mode="host",
            wifi_ssid="Test",
            wifi_password="password123",
            encryption_key="0123456789ABCDEF0123456789ABCDEF"
        )
        assert config.mode == "host"
        
        # Modo inválido
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(
                mode="invalid",
                wifi_ssid="Test",
                wifi_password="password123",
                encryption_key="0123456789ABCDEF0123456789ABCDEF"
            )
        
        assert "Modo debe ser 'client' o 'host'" in str(exc_info.value)
    
    def test_wifi_ssid_validation(self):
        """Test validación de SSID Wi-Fi."""
        base_config = {
            "mode": "client",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # SSID válido normal
        config = BomberCatConfig(wifi_ssid="TestNetwork", **base_config)
        assert config.wifi_ssid == "TestNetwork"
        
        # SSID válido con espacios (se recortan)
        config = BomberCatConfig(wifi_ssid="  TestNetwork  ", **base_config)
        assert config.wifi_ssid == "TestNetwork"
        
        # SSID de 32 caracteres (límite)
        long_ssid = "A" * 32
        config = BomberCatConfig(wifi_ssid=long_ssid, **base_config)
        assert config.wifi_ssid == long_ssid
        
        # SSID vacío
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_ssid="", **base_config)
        assert "SSID no puede estar vacío" in str(exc_info.value)
        
        # SSID solo espacios
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_ssid="   ", **base_config)
        assert "SSID no puede estar vacío" in str(exc_info.value)
        
        # SSID demasiado largo (33 caracteres)
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_ssid="A" * 33, **base_config)
        assert "excede 32 bytes" in str(exc_info.value)
        
        # SSID con caracteres de control
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_ssid="Test\x00Network", **base_config)
        assert "caracteres de control" in str(exc_info.value)
        
        # SSID con caracteres UTF-8 que exceden 32 bytes
        utf8_ssid = "测试网络" * 6  # Caracteres chinos que exceden 32 bytes
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_ssid=utf8_ssid, **base_config)
        assert "excede 32 bytes" in str(exc_info.value)
    
    def test_wifi_password_validation(self):
        """Test validación de contraseña Wi-Fi."""
        base_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Contraseña válida mínima (8 caracteres)
        config = BomberCatConfig(wifi_password="12345678", **base_config)
        assert config.wifi_password == "12345678"
        
        # Contraseña válida máxima (64 caracteres)
        long_password = "A" * 64
        config = BomberCatConfig(wifi_password=long_password, **base_config)
        assert config.wifi_password == long_password
        
        # Contraseña demasiado corta (7 caracteres)
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_password="1234567", **base_config)
        assert "al menos 8 caracteres" in str(exc_info.value)
        
        # Contraseña demasiado larga (65 caracteres)
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_password="A" * 65, **base_config)
        assert "no puede exceder 64 caracteres" in str(exc_info.value)
        
        # Contraseña con caracteres de control
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(wifi_password="pass\x00word", **base_config)
        assert "caracteres de control" in str(exc_info.value)
    
    def test_encryption_key_validation(self):
        """Test validación de clave de encriptación."""
        base_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123"
        }
        
        # Clave válida en minúsculas
        config = BomberCatConfig(
            encryption_key="0123456789abcdef0123456789abcdef",
            **base_config
        )
        assert config.encryption_key == "0123456789ABCDEF0123456789ABCDEF"
        
        # Clave válida en mayúsculas
        config = BomberCatConfig(
            encryption_key="0123456789ABCDEF0123456789ABCDEF",
            **base_config
        )
        assert config.encryption_key == "0123456789ABCDEF0123456789ABCDEF"
        
        # Clave válida mixta
        config = BomberCatConfig(
            encryption_key="0123456789AbCdEf0123456789AbCdEf",
            **base_config
        )
        assert config.encryption_key == "0123456789ABCDEF0123456789ABCDEF"
        
        # Clave vacía
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(encryption_key="", **base_config)
        assert "no puede estar vacía" in str(exc_info.value)
        
        # Clave demasiado corta (31 caracteres)
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(
                encryption_key="0123456789ABCDEF0123456789ABCDE",
                **base_config
            )
        assert "exactamente 32 caracteres" in str(exc_info.value)
        
        # Clave demasiado larga (33 caracteres)
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(
                encryption_key="0123456789ABCDEF0123456789ABCDEF0",
                **base_config
            )
        assert "exactamente 32 caracteres" in str(exc_info.value)
        
        # Clave con caracteres no hexadecimales
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(
                encryption_key="0123456789ABCDEFG123456789ABCDEF",
                **base_config
            )
        assert "caracteres hexadecimales" in str(exc_info.value)
        
        # Clave con espacios
        with pytest.raises(ValidationError) as exc_info:
            BomberCatConfig(
                encryption_key="0123456789ABCDEF 123456789ABCDEF",
                **base_config
            )
        assert "caracteres hexadecimales" in str(exc_info.value)
    
    def test_to_device_dict(self):
        """Test conversión a diccionario para dispositivo."""
        config = BomberCatConfig(
            mode="client",
            wifi_ssid="TestNetwork",
            wifi_password="password123",
            encryption_key="0123456789abcdef0123456789abcdef"
        )
        
        device_dict = config.to_device_dict()
        
        expected = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        assert device_dict == expected


class TestConfigValidator:
    """Tests para la clase ConfigValidator."""
    
    def test_validate_config_success(self):
        """Test validación exitosa."""
        config_data = {
            "mode": "host",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        config = ConfigValidator.validate_config(config_data)
        
        assert isinstance(config, BomberCatConfig)
        assert config.mode == "host"
    
    def test_validate_config_failure(self):
        """Test validación con error."""
        config_data = {
            "mode": "invalid",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        with pytest.raises(ValidationError):
            ConfigValidator.validate_config(config_data)
    
    def test_validate_partial_config(self):
        """Test validación de configuración parcial."""
        current_config = BomberCatConfig(
            mode="client",
            wifi_ssid="OldNetwork",
            wifi_password="oldpassword",
            encryption_key="0123456789ABCDEF0123456789ABCDEF"
        )
        
        partial_data = {
            "wifi_ssid": "NewNetwork",
            "wifi_password": "newpassword"
        }
        
        merged_config = ConfigValidator.validate_partial_config(
            partial_data, current_config
        )
        
        assert merged_config.mode == "client"  # Mantenido
        assert merged_config.wifi_ssid == "NewNetwork"  # Actualizado
        assert merged_config.wifi_password == "newpassword"  # Actualizado
        assert merged_config.encryption_key == "0123456789ABCDEF0123456789ABCDEF"  # Mantenido
    
    def test_get_validation_errors(self):
        """Test obtención de errores sin excepción."""
        # Configuración válida
        valid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        errors = ConfigValidator.get_validation_errors(valid_config)
        assert errors == []
        
        # Configuración inválida
        invalid_config = {
            "mode": "invalid",
            "wifi_ssid": "",
            "wifi_password": "123",
            "encryption_key": "invalid"
        }
        
        errors = ConfigValidator.get_validation_errors(invalid_config)
        assert len(errors) > 0
        assert any("modo" in error.lower() for error in errors)
    
    def test_is_valid_config(self):
        """Test verificación de validez."""
        valid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        assert ConfigValidator.is_valid_config(valid_config) is True
        
        invalid_config = {
            "mode": "invalid",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        assert ConfigValidator.is_valid_config(invalid_config) is False
    
    def test_sanitize_config(self):
        """Test sanitización de configuración."""
        dirty_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF",
            "invalid_field": "should_be_removed",
            "another_invalid": 123
        }
        
        clean_config = ConfigValidator.sanitize_config(dirty_config)
        
        expected = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        assert clean_config == expected


class TestConvenienceFunctions:
    """Tests para funciones de conveniencia."""
    
    def test_validate_mode(self):
        """Test validación de modo."""
        assert validate_mode("client") is True
        assert validate_mode("host") is True
        assert validate_mode("CLIENT") is True
        assert validate_mode("HOST") is True
        assert validate_mode("invalid") is False
        assert validate_mode("") is False
    
    def test_validate_wifi_ssid(self):
        """Test validación de SSID."""
        assert validate_wifi_ssid("TestNetwork") is True
        assert validate_wifi_ssid("A" * 32) is True
        assert validate_wifi_ssid("") is False
        assert validate_wifi_ssid("A" * 33) is False
        assert validate_wifi_ssid("Test\x00Network") is False
    
    def test_validate_wifi_password(self):
        """Test validación de contraseña."""
        assert validate_wifi_password("12345678") is True
        assert validate_wifi_password("A" * 64) is True
        assert validate_wifi_password("1234567") is False
        assert validate_wifi_password("A" * 65) is False
        assert validate_wifi_password("pass\x00word") is False
    
    def test_validate_encryption_key(self):
        """Test validación de clave de encriptación."""
        assert validate_encryption_key("0123456789ABCDEF0123456789ABCDEF") is True
        assert validate_encryption_key("0123456789abcdef0123456789abcdef") is True
        assert validate_encryption_key("0123456789ABCDEF0123456789ABCDE") is False
        assert validate_encryption_key("0123456789ABCDEF0123456789ABCDEF0") is False
        assert validate_encryption_key("0123456789ABCDEFG123456789ABCDEF") is False
        assert validate_encryption_key("") is False


class TestEdgeCases:
    """Tests para casos límite específicos."""
    
    def test_unicode_ssid_edge_cases(self):
        """Test casos límite con SSID Unicode."""
        base_config = {
            "mode": "client",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # SSID con emojis (pueden exceder 32 bytes)
        emoji_ssid = "Test🚀Network"
        if len(emoji_ssid.encode('utf-8')) <= 32:
            config = BomberCatConfig(wifi_ssid=emoji_ssid, **base_config)
            assert config.wifi_ssid == emoji_ssid
        else:
            with pytest.raises(ValidationError):
                BomberCatConfig(wifi_ssid=emoji_ssid, **base_config)
        
        # SSID con caracteres acentuados
        accented_ssid = "Café_Network"
        config = BomberCatConfig(wifi_ssid=accented_ssid, **base_config)
        assert config.wifi_ssid == accented_ssid
    
    def test_boundary_values(self):
        """Test valores en los límites exactos."""
        base_config = {
            "mode": "client",
            "wifi_ssid": "Test",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Contraseña de exactamente 8 caracteres
        config = BomberCatConfig(wifi_password="12345678", **base_config)
        assert len(config.wifi_password) == 8
        
        # Contraseña de exactamente 64 caracteres
        password_64 = "A" * 64
        config = BomberCatConfig(wifi_password=password_64, **base_config)
        assert len(config.wifi_password) == 64
    
    def test_case_sensitivity(self):
        """Test sensibilidad a mayúsculas/minúsculas."""
        base_config = {
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Modo en diferentes casos
        for mode in ["client", "CLIENT", "Client", "cLiEnT"]:
            config = BomberCatConfig(mode=mode, **base_config)
            assert config.mode == "client"
        
        for mode in ["host", "HOST", "Host", "hOsT"]:
            config = BomberCatConfig(mode=mode, **base_config)
            assert config.mode == "host"
        
        # Clave de encriptación en diferentes casos
        for key in ["0123456789abcdef0123456789abcdef", 
                   "0123456789ABCDEF0123456789ABCDEF",
                   "0123456789AbCdEf0123456789aBcDeF"]:
            config = BomberCatConfig(encryption_key=key, **base_config)
            assert config.encryption_key == "0123456789ABCDEF0123456789ABCDEF"