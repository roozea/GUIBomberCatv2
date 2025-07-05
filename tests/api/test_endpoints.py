"""Tests para endpoints REST de la API."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app


class TestRESTEndpoints:
    """Tests para endpoints REST."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba FastAPI."""
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test endpoint raíz."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "BomberCat Integrator API"
        assert data["version"] == "2.0"
        assert "endpoints" in data
        assert "docs" in data
        assert "websocket" in data
    
    def test_health_endpoint(self, client):
        """Test endpoint de health check."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_status_endpoint(self, client):
        """Test endpoint de status."""
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "running"
        assert "timestamp" in data
        assert "services" in data
        assert "device" in data
        assert "relay" in data
        assert "mqtt" in data
        assert "websocket_connections" in data
        
        # Verificar estructura de servicios
        services = data["services"]
        assert "flash_service" in services
        assert "config_service" in services
        assert "relay_service" in services
        assert "mqtt_service" in services
    
    @patch('api.main.flash_service')
    def test_flash_endpoint_success(self, mock_flash_service, client):
        """Test endpoint de flash exitoso."""
        # Mock del flash service
        mock_flash_service.flash_firmware = AsyncMock(return_value={
            "success": True,
            "message": "Flash completado"
        })
        
        flash_request = {
            "firmware_path": "/path/to/firmware.bin",
            "port": "/dev/ttyUSB0"
        }
        
        response = client.post("/flash", json=flash_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "started"
        assert data["message"] == "Flash iniciado"
        assert data["firmware_path"] == flash_request["firmware_path"]
        assert data["port"] == flash_request["port"]
    
    @patch('api.main.flash_service', None)
    def test_flash_endpoint_service_unavailable(self, client):
        """Test endpoint de flash con servicio no disponible."""
        flash_request = {
            "firmware_path": "/path/to/firmware.bin",
            "port": "/dev/ttyUSB0"
        }
        
        response = client.post("/flash", json=flash_request)
        assert response.status_code == 503
        
        data = response.json()
        assert "Flash service no disponible" in data["detail"]
    
    @patch('api.main.config_service')
    def test_config_endpoint_success(self, mock_config_service, client):
        """Test endpoint de configuración exitoso."""
        # Mock del config service
        mock_config_service.update_config = AsyncMock(return_value={
            "success": True,
            "updated_config": {"wifi_ssid": "TestWiFi"}
        })
        
        config_request = {
            "config_data": {
                "wifi_ssid": "TestWiFi",
                "wifi_password": "password123"
            }
        }
        
        response = client.post("/config", json=config_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Configuración actualizada"
        assert "result" in data
    
    @patch('api.main.config_service', None)
    def test_config_endpoint_service_unavailable(self, client):
        """Test endpoint de configuración con servicio no disponible."""
        config_request = {
            "config_data": {"wifi_ssid": "TestWiFi"}
        }
        
        response = client.post("/config", json=config_request)
        assert response.status_code == 503
        
        data = response.json()
        assert "Config service no disponible" in data["detail"]
    
    @patch('api.main.relay_service')
    def test_relay_start_endpoint_success(self, mock_relay_service, client):
        """Test endpoint de inicio de relay exitoso."""
        # Mock del relay service
        mock_relay_service.start_relay = AsyncMock(return_value={
            "success": True,
            "message": "Relay iniciado"
        })
        
        relay_request = {
            "source_port": 8080,
            "target_host": "192.168.1.100",
            "target_port": 80
        }
        
        response = client.post("/relay/start", json=relay_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "started"
        assert data["message"] == "Relay iniciado"
        assert "config" in data
        assert data["config"]["source_port"] == 8080
        assert data["config"]["target_host"] == "192.168.1.100"
        assert data["config"]["target_port"] == 80
    
    @patch('api.main.relay_service', None)
    def test_relay_start_endpoint_service_unavailable(self, client):
        """Test endpoint de inicio de relay con servicio no disponible."""
        relay_request = {
            "source_port": 8080,
            "target_host": "192.168.1.100",
            "target_port": 80
        }
        
        response = client.post("/relay/start", json=relay_request)
        assert response.status_code == 503
        
        data = response.json()
        assert "Relay service no disponible" in data["detail"]
    
    @patch('api.main.relay_service')
    def test_relay_stop_endpoint_success(self, mock_relay_service, client):
        """Test endpoint de detención de relay exitoso."""
        # Mock del relay service
        mock_relay_service.stop_relay = AsyncMock(return_value={
            "success": True,
            "message": "Relay detenido"
        })
        
        response = client.post("/relay/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "stopped"
        assert data["message"] == "Relay detenido"
        assert "result" in data
    
    @patch('api.main.relay_service', None)
    def test_relay_stop_endpoint_service_unavailable(self, client):
        """Test endpoint de detención de relay con servicio no disponible."""
        response = client.post("/relay/stop")
        assert response.status_code == 503
        
        data = response.json()
        assert "Relay service no disponible" in data["detail"]
    
    def test_flash_endpoint_invalid_request(self, client):
        """Test endpoint de flash con request inválido."""
        # Request sin campos requeridos
        invalid_request = {"invalid_field": "value"}
        
        response = client.post("/flash", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    def test_config_endpoint_invalid_request(self, client):
        """Test endpoint de configuración con request inválido."""
        # Request sin campos requeridos
        invalid_request = {"invalid_field": "value"}
        
        response = client.post("/config", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    def test_relay_start_endpoint_invalid_request(self, client):
        """Test endpoint de inicio de relay con request inválido."""
        # Request con tipos incorrectos
        invalid_request = {
            "source_port": "not_a_number",
            "target_host": "192.168.1.100",
            "target_port": 80
        }
        
        response = client.post("/relay/start", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    @patch('api.main.flash_service')
    def test_flash_endpoint_service_error(self, mock_flash_service, client):
        """Test endpoint de flash con error en el servicio."""
        # Mock que lanza excepción
        mock_flash_service.flash_firmware = AsyncMock(side_effect=Exception("Service error"))
        
        flash_request = {
            "firmware_path": "/path/to/firmware.bin",
            "port": "/dev/ttyUSB0"
        }
        
        response = client.post("/flash", json=flash_request)
        assert response.status_code == 500
        
        data = response.json()
        assert "Service error" in data["detail"]
    
    @patch('api.main.config_service')
    def test_config_endpoint_service_error(self, mock_config_service, client):
        """Test endpoint de configuración con error en el servicio."""
        # Mock que lanza excepción
        mock_config_service.update_config = AsyncMock(side_effect=Exception("Config error"))
        
        config_request = {
            "config_data": {"wifi_ssid": "TestWiFi"}
        }
        
        response = client.post("/config", json=config_request)
        assert response.status_code == 500
        
        data = response.json()
        assert "Config error" in data["detail"]
    
    @patch('api.main.relay_service')
    def test_relay_start_endpoint_service_error(self, mock_relay_service, client):
        """Test endpoint de inicio de relay con error en el servicio."""
        # Mock que lanza excepción
        mock_relay_service.start_relay = AsyncMock(side_effect=Exception("Relay error"))
        
        relay_request = {
            "source_port": 8080,
            "target_host": "192.168.1.100",
            "target_port": 80
        }
        
        response = client.post("/relay/start", json=relay_request)
        assert response.status_code == 500
        
        data = response.json()
        assert "Relay error" in data["detail"]
    
    def test_nonexistent_endpoint(self, client):
        """Test endpoint que no existe."""
        response = client.get("/nonexistent")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test método HTTP no permitido."""
        # Intentar GET en endpoint que solo acepta POST
        response = client.get("/flash")
        assert response.status_code == 405


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main(["-v", __file__])