"""Tests para endpoints de configuración BomberCat.

Este módulo contiene pruebas de integración para los endpoints
de la API de configuración usando httpx.AsyncClient.
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
import serial

from api.routers.config import router as config_router
from modules.bombercat_config.validators import BomberCatConfig
from modules.bombercat_config.backup import ConfigBackupManager, BackupError, RollbackError
from modules.bombercat_config.transaction import TransactionError


# Crear app de prueba
test_app = FastAPI()
test_app.include_router(config_router, prefix="/config")


class TestConfigEndpoints:
    """Tests para endpoints de configuración."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    @pytest.fixture
    async def async_client(self):
        """Cliente asíncrono para pruebas."""
        async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def valid_config(self):
        """Configuración válida para pruebas."""
        return {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
    
    @pytest.fixture
    def mock_serial_port(self):
        """Mock de puerto serie."""
        mock_port = Mock(spec=serial.Serial)
        mock_port.reset_input_buffer = Mock()
        mock_port.write = Mock()
        mock_port.flush = Mock()
        mock_port.in_waiting = 1
        mock_port.read = Mock()
        return mock_port


class TestPostConfigEndpoint:
    """Tests para POST /config endpoint."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    @pytest.fixture
    def valid_config(self):
        """Configuración válida para pruebas."""
        return {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
    
    @patch('api.routers.config.apply_config_with_transaction')
    @patch('api.routers.config.get_serial_port')
    def test_post_config_success(self, mock_get_port, mock_apply_config, client, valid_config):
        """Test aplicación exitosa de configuración."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        mock_apply_config.return_value = {"status": "OK", "message": "Configuración aplicada"}
        
        response = client.post("/config/", json=valid_config)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "OK"
        assert "Configuración aplicada exitosamente" in response_data["message"]
        
        mock_apply_config.assert_called_once()
        call_args = mock_apply_config.call_args
        assert call_args[0][0] == mock_port  # Puerto serie
        assert call_args[0][1] == valid_config  # Configuración
    
    def test_post_config_invalid_mode(self, client):
        """Test con modo inválido."""
        invalid_config = {
            "mode": "invalid_mode",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        response = client.post("/config/", json=invalid_config)
        
        assert response.status_code == 422
        response_data = response.json()
        assert "validation error" in response_data["detail"][0]["msg"].lower()
    
    def test_post_config_invalid_wifi_ssid(self, client):
        """Test con SSID WiFi inválido."""
        invalid_config = {
            "mode": "client",
            "wifi_ssid": "A" * 33,  # Muy largo
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        response = client.post("/config/", json=invalid_config)
        
        assert response.status_code == 422
        response_data = response.json()
        assert any("wifi_ssid" in str(error) for error in response_data["detail"])
    
    def test_post_config_invalid_encryption_key(self, client):
        """Test con clave de encriptación inválida."""
        invalid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "INVALID_KEY"  # No es hexadecimal de 32 caracteres
        }
        
        response = client.post("/config/", json=invalid_config)
        
        assert response.status_code == 422
        response_data = response.json()
        assert any("encryption_key" in str(error) for error in response_data["detail"])
    
    @patch('api.routers.config.apply_config_with_transaction')
    @patch('api.routers.config.get_serial_port')
    def test_post_config_transaction_error(self, mock_get_port, mock_apply_config, client, valid_config):
        """Test error en transacción."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        mock_apply_config.side_effect = TransactionError("Error en transacción")
        
        response = client.post("/config/", json=valid_config)
        
        assert response.status_code == 400
        response_data = response.json()
        assert "Error en transacción" in response_data["detail"]
    
    @patch('api.routers.config.apply_config_with_transaction')
    @patch('api.routers.config.get_serial_port')
    def test_post_config_serial_error(self, mock_get_port, mock_apply_config, client, valid_config):
        """Test error de comunicación serie."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        mock_apply_config.side_effect = serial.SerialException("Error de comunicación")
        
        response = client.post("/config/", json=valid_config)
        
        assert response.status_code == 503
        response_data = response.json()
        assert "Error de comunicación" in response_data["detail"]
    
    def test_post_config_missing_fields(self, client):
        """Test con campos faltantes."""
        incomplete_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork"
            # Faltan wifi_password y encryption_key
        }
        
        response = client.post("/config/", json=incomplete_config)
        
        assert response.status_code == 422
        response_data = response.json()
        assert len(response_data["detail"]) >= 2  # Al menos 2 campos faltantes


class TestGetConfigStatusEndpoint:
    """Tests para GET /config/status endpoint."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    @patch('api.routers.config.send_command_with_retry')
    @patch('api.routers.config.get_serial_port')
    def test_get_status_success(self, mock_get_port, mock_send_command, client):
        """Test obtención exitosa de estado."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        expected_status = {
            "status": "OK",
            "data": {
                "mode": "client",
                "wifi_ssid": "CurrentNetwork",
                "wifi_connected": True,
                "nvs_status": "healthy",
                "last_update": "2024-01-15T10:30:00Z"
            }
        }
        
        mock_send_command.return_value = expected_status
        
        response = client.get("/config/status")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "OK"
        assert response_data["data"]["mode"] == "client"
        assert response_data["data"]["wifi_ssid"] == "CurrentNetwork"
        
        mock_send_command.assert_called_once_with(mock_port, "GET_CONFIG")
    
    @patch('api.routers.config.send_command_with_retry')
    @patch('api.routers.config.get_serial_port')
    def test_get_status_device_error(self, mock_get_port, mock_send_command, client):
        """Test error del dispositivo."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        mock_send_command.return_value = {
            "status": "ERR",
            "msg": "NVS corrupted"
        }
        
        response = client.get("/config/status")
        
        assert response.status_code == 400
        response_data = response.json()
        assert "NVS corrupted" in response_data["detail"]
    
    @patch('api.routers.config.send_command_with_retry')
    @patch('api.routers.config.get_serial_port')
    def test_get_status_communication_error(self, mock_get_port, mock_send_command, client):
        """Test error de comunicación."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        from fastapi import HTTPException
        mock_send_command.side_effect = HTTPException(status_code=503, detail="Communication timeout")
        
        response = client.get("/config/status")
        
        assert response.status_code == 503
        response_data = response.json()
        assert "Communication timeout" in response_data["detail"]


class TestPostConfigVerifyEndpoint:
    """Tests para POST /config/verify endpoint."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    @patch('api.routers.config.send_command_with_retry')
    @patch('api.routers.config.get_serial_port')
    def test_verify_success(self, mock_get_port, mock_send_command, client):
        """Test verificación exitosa."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        mock_send_command.return_value = {
            "status": "OK",
            "data": {
                "config_valid": True,
                "nvs_integrity": "OK",
                "wifi_test": "PASS"
            }
        }
        
        response = client.post("/config/verify")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "OK"
        assert response_data["verified"] is True
        assert "Configuración verificada exitosamente" in response_data["message"]
        
        mock_send_command.assert_called_once_with(mock_port, "VERIFY_CONFIG")
    
    @patch('api.routers.config.send_command_with_retry')
    @patch('api.routers.config.get_serial_port')
    def test_verify_failure(self, mock_get_port, mock_send_command, client):
        """Test fallo en verificación."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        mock_send_command.return_value = {
            "status": "ERR",
            "msg": "Configuration invalid",
            "data": {
                "config_valid": False,
                "errors": ["Invalid WiFi credentials"]
            }
        }
        
        response = client.post("/config/verify")
        
        assert response.status_code == 400
        response_data = response.json()
        assert "Configuration invalid" in response_data["detail"]


class TestPostConfigRollbackEndpoint:
    """Tests para POST /config/rollback endpoint."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    @patch('api.routers.config.backup_manager')
    @patch('api.routers.config.get_serial_port')
    def test_rollback_success(self, mock_get_port, mock_backup_manager, client):
        """Test rollback exitoso."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        backup_config = {
            "mode": "client",
            "wifi_ssid": "BackupNetwork",
            "wifi_password": "backuppass",
            "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
        }
        
        mock_backup_manager.get_latest_backup.return_value = backup_config
        mock_backup_manager.rollback.return_value = True
        
        response = client.post("/config/rollback")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "OK"
        assert "Rollback completado exitosamente" in response_data["message"]
        assert response_data["restored_config"] == backup_config
        
        mock_backup_manager.rollback.assert_called_once_with(mock_port, backup_config)
    
    @patch('api.routers.config.backup_manager')
    @patch('api.routers.config.get_serial_port')
    def test_rollback_no_backup(self, mock_get_port, mock_backup_manager, client):
        """Test rollback sin backup disponible."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        mock_backup_manager.get_latest_backup.return_value = None
        
        response = client.post("/config/rollback")
        
        assert response.status_code == 404
        response_data = response.json()
        assert "No hay backup disponible" in response_data["detail"]
    
    @patch('api.routers.config.backup_manager')
    @patch('api.routers.config.get_serial_port')
    def test_rollback_failure(self, mock_get_port, mock_backup_manager, client):
        """Test fallo en rollback."""
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        
        backup_config = {
            "mode": "client",
            "wifi_ssid": "BackupNetwork",
            "wifi_password": "backuppass",
            "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
        }
        
        mock_backup_manager.get_latest_backup.return_value = backup_config
        mock_backup_manager.rollback.side_effect = RollbackError("Rollback failed")
        
        response = client.post("/config/rollback")
        
        assert response.status_code == 500
        response_data = response.json()
        assert "Error en rollback" in response_data["detail"]


class TestDeleteConfigBackupEndpoint:
    """Tests para DELETE /config/backup endpoint."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    @patch('api.routers.config.backup_manager')
    def test_cleanup_backups_success(self, mock_backup_manager, client):
        """Test limpieza exitosa de backups."""
        mock_backup_manager.cleanup_old_backups.return_value = 3  # 3 backups eliminados
        
        response = client.delete("/config/backup?keep=5")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "OK"
        assert response_data["deleted_count"] == 3
        assert "3 backups antiguos eliminados" in response_data["message"]
        
        mock_backup_manager.cleanup_old_backups.assert_called_once_with(keep=5)
    
    @patch('api.routers.config.backup_manager')
    def test_cleanup_backups_default_keep(self, mock_backup_manager, client):
        """Test limpieza con valor por defecto."""
        mock_backup_manager.cleanup_old_backups.return_value = 1
        
        response = client.delete("/config/backup")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["deleted_count"] == 1
        
        mock_backup_manager.cleanup_old_backups.assert_called_once_with(keep=10)
    
    @patch('api.routers.config.backup_manager')
    def test_cleanup_backups_invalid_keep(self, mock_backup_manager, client):
        """Test limpieza con parámetro inválido."""
        response = client.delete("/config/backup?keep=0")
        
        assert response.status_code == 422
        response_data = response.json()
        assert "validation error" in response_data["detail"][0]["msg"].lower()
    
    @patch('api.routers.config.backup_manager')
    def test_cleanup_backups_error(self, mock_backup_manager, client):
        """Test error en limpieza de backups."""
        mock_backup_manager.cleanup_old_backups.side_effect = Exception("Cleanup error")
        
        response = client.delete("/config/backup")
        
        assert response.status_code == 500
        response_data = response.json()
        assert "Error en limpieza" in response_data["detail"]


class TestAsyncEndpoints:
    """Tests asíncronos para endpoints."""
    
    @pytest.mark.asyncio
    async def test_post_config_async(self):
        """Test endpoint POST /config de forma asíncrona."""
        valid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        with patch('api.routers.config.apply_config_with_transaction') as mock_apply:
            with patch('api.routers.config.get_serial_port') as mock_get_port:
                mock_port = Mock()
                mock_get_port.return_value = mock_port
                mock_apply.return_value = {"status": "OK", "message": "Success"}
                
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    response = await client.post("/config/", json=valid_config)
                    
                    assert response.status_code == 200
                    response_data = response.json()
                    assert response_data["status"] == "OK"
    
    @pytest.mark.asyncio
    async def test_get_status_async(self):
        """Test endpoint GET /config/status de forma asíncrona."""
        expected_status = {
            "status": "OK",
            "data": {
                "mode": "client",
                "wifi_ssid": "CurrentNetwork",
                "wifi_connected": True
            }
        }
        
        with patch('api.routers.config.send_command_with_retry') as mock_send:
            with patch('api.routers.config.get_serial_port') as mock_get_port:
                mock_port = Mock()
                mock_get_port.return_value = mock_port
                mock_send.return_value = expected_status
                
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    response = await client.get("/config/status")
                    
                    assert response.status_code == 200
                    response_data = response.json()
                    assert response_data["status"] == "OK"
                    assert response_data["data"]["mode"] == "client"
    
    @pytest.mark.asyncio
    async def test_verify_config_async(self):
        """Test endpoint POST /config/verify de forma asíncrona."""
        verify_response = {
            "status": "OK",
            "data": {
                "config_valid": True,
                "nvs_integrity": "OK"
            }
        }
        
        with patch('api.routers.config.send_command_with_retry') as mock_send:
            with patch('api.routers.config.get_serial_port') as mock_get_port:
                mock_port = Mock()
                mock_get_port.return_value = mock_port
                mock_send.return_value = verify_response
                
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    response = await client.post("/config/verify")
                    
                    assert response.status_code == 200
                    response_data = response.json()
                    assert response_data["status"] == "OK"
                    assert response_data["verified"] is True


class TestErrorHandling:
    """Tests para manejo de errores."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI."""
        return TestClient(test_app)
    
    def test_validation_error_handler(self, client):
        """Test manejador de errores de validación."""
        invalid_config = {
            "mode": "invalid",
            "wifi_ssid": "",
            "wifi_password": "123",  # Muy corto
            "encryption_key": "invalid"
        }
        
        response = client.post("/config/", json=invalid_config)
        
        assert response.status_code == 422
        response_data = response.json()
        assert "detail" in response_data
        assert isinstance(response_data["detail"], list)
        assert len(response_data["detail"]) > 0
    
    @patch('api.routers.config.apply_config_with_transaction')
    @patch('api.routers.config.get_serial_port')
    def test_serial_exception_handler(self, mock_get_port, mock_apply_config, client):
        """Test manejador de excepciones serie."""
        valid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        mock_port = Mock()
        mock_get_port.return_value = mock_port
        mock_apply_config.side_effect = serial.SerialException("Port not available")
        
        response = client.post("/config/", json=valid_config)
        
        assert response.status_code == 503
        response_data = response.json()
        assert "Error de comunicación" in response_data["detail"]
        assert "Port not available" in response_data["detail"]
    
    @patch('api.routers.config.get_serial_port')
    def test_generic_exception_handler(self, mock_get_port, client):
        """Test manejador de excepciones genéricas."""
        valid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        mock_get_port.side_effect = Exception("Unexpected error")
        
        response = client.post("/config/", json=valid_config)
        
        assert response.status_code == 500
        response_data = response.json()
        assert "Error interno del servidor" in response_data["detail"]


class TestConcurrentRequests:
    """Tests para solicitudes concurrentes."""
    
    @pytest.mark.asyncio
    async def test_concurrent_config_requests(self):
        """Test solicitudes concurrentes de configuración."""
        valid_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        with patch('api.routers.config.apply_config_with_transaction') as mock_apply:
            with patch('api.routers.config.get_serial_port') as mock_get_port:
                mock_port = Mock()
                mock_get_port.return_value = mock_port
                mock_apply.return_value = {"status": "OK", "message": "Success"}
                
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    # Enviar múltiples solicitudes concurrentes
                    tasks = [
                        client.post("/config/", json=valid_config)
                        for _ in range(3)
                    ]
                    
                    responses = await asyncio.gather(*tasks)
                    
                    # Todas las respuestas deben ser exitosas
                    for response in responses:
                        assert response.status_code == 200
                        response_data = response.json()
                        assert response_data["status"] == "OK"
                    
                    # Verificar que se llamó apply_config_with_transaction para cada solicitud
                    assert mock_apply.call_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_status_requests(self):
        """Test solicitudes concurrentes de estado."""
        expected_status = {
            "status": "OK",
            "data": {
                "mode": "client",
                "wifi_ssid": "CurrentNetwork",
                "wifi_connected": True
            }
        }
        
        with patch('api.routers.config.send_command_with_retry') as mock_send:
            with patch('api.routers.config.get_serial_port') as mock_get_port:
                mock_port = Mock()
                mock_get_port.return_value = mock_port
                mock_send.return_value = expected_status
                
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    # Enviar múltiples solicitudes de estado concurrentes
                    tasks = [
                        client.get("/config/status")
                        for _ in range(5)
                    ]
                    
                    responses = await asyncio.gather(*tasks)
                    
                    # Todas las respuestas deben ser exitosas
                    for response in responses:
                        assert response.status_code == 200
                        response_data = response.json()
                        assert response_data["status"] == "OK"
                    
                    # Verificar que se llamó send_command_with_retry para cada solicitud
                    assert mock_send.call_count == 5