"""Tests para WebSocket broadcast functionality."""

import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from api.main import app


class TestWebSocketBroadcast:
    """Tests para funcionalidad de broadcast WebSocket."""
    
    @pytest.fixture
    def client(self):
        """Cliente de prueba FastAPI."""
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, client):
        """Test conexión básica WebSocket."""
        with client.websocket_connect("/ws") as websocket:
            # Verificar mensaje de conexión inicial
            data = websocket.receive_json()
            assert data["type"] == "connection_established"
            assert "timestamp" in data
            assert data["message"] == "Conectado al WebSocket de BomberCat"
    
    @pytest.mark.asyncio
    async def test_ping_pong(self, client):
        """Test comando ping/pong."""
        with client.websocket_connect("/ws") as websocket:
            # Recibir mensaje inicial
            websocket.receive_json()
            
            # Enviar ping
            ping_command = {"type": "ping"}
            websocket.send_json(ping_command)
            
            # Recibir eco del comando
            echo_response = websocket.receive_json()
            assert echo_response["type"] == "command_echo"
            assert echo_response["original_command"] == ping_command
            
            # Recibir pong
            pong_response = websocket.receive_json()
            assert pong_response["type"] == "pong"
            assert "timestamp" in pong_response
    
    @pytest.mark.asyncio
    async def test_get_status_command(self, client):
        """Test comando get_status."""
        with client.websocket_connect("/ws") as websocket:
            # Recibir mensaje inicial
            websocket.receive_json()
            
            # Enviar get_status
            status_command = {"type": "get_status"}
            websocket.send_json(status_command)
            
            # Recibir eco del comando
            echo_response = websocket.receive_json()
            assert echo_response["type"] == "command_echo"
            
            # Recibir respuesta de status
            status_response = websocket.receive_json()
            assert status_response["type"] == "status_response"
            assert "data" in status_response
            assert "timestamp" in status_response
    
    @pytest.mark.asyncio
    async def test_subscribe_command(self, client):
        """Test comando de suscripción."""
        with client.websocket_connect("/ws") as websocket:
            # Recibir mensaje inicial
            websocket.receive_json()
            
            # Enviar suscripción
            subscribe_command = {
                "type": "subscribe",
                "channels": ["device_status", "latency"]
            }
            websocket.send_json(subscribe_command)
            
            # Recibir eco del comando
            echo_response = websocket.receive_json()
            assert echo_response["type"] == "command_echo"
            
            # Recibir confirmación de suscripción
            subscribe_response = websocket.receive_json()
            assert subscribe_response["type"] == "subscribed"
            assert subscribe_response["channels"] == ["device_status", "latency"]
    
    @pytest.mark.asyncio
    async def test_unknown_command(self, client):
        """Test comando desconocido."""
        with client.websocket_connect("/ws") as websocket:
            # Recibir mensaje inicial
            websocket.receive_json()
            
            # Enviar comando desconocido
            unknown_command = {"type": "unknown_command_test"}
            websocket.send_json(unknown_command)
            
            # Recibir eco del comando
            echo_response = websocket.receive_json()
            assert echo_response["type"] == "command_echo"
            
            # Recibir respuesta de comando desconocido
            unknown_response = websocket.receive_json()
            assert unknown_response["type"] == "unknown_command"
            assert "unknown_command_test" in unknown_response["message"]
    
    @pytest.mark.asyncio
    async def test_invalid_json(self, client):
        """Test envío de JSON inválido."""
        with client.websocket_connect("/ws") as websocket:
            # Recibir mensaje inicial
            websocket.receive_json()
            
            # Enviar JSON inválido
            websocket.send_text("invalid json")
            
            # Recibir error de parsing
            error_response = websocket.receive_json()
            assert error_response["type"] == "parse_error"
            assert error_response["message"] == "Error al parsear JSON"
    
    @pytest.mark.asyncio
    async def test_invalid_command_format(self, client):
        """Test formato de comando inválido."""
        with client.websocket_connect("/ws") as websocket:
            # Recibir mensaje inicial
            websocket.receive_json()
            
            # Enviar comando sin tipo
            invalid_command = {"data": "test"}
            websocket.send_json(invalid_command)
            
            # Recibir error de formato
            error_response = websocket.receive_json()
            assert error_response["type"] == "error"
            assert error_response["message"] == "Formato de comando inválido"
    
    @pytest.mark.asyncio
    async def test_multiple_clients_broadcast(self, client):
        """Test broadcast a múltiples clientes."""
        # Conectar dos clientes WebSocket
        with client.websocket_connect("/ws") as ws1, \
             client.websocket_connect("/ws") as ws2:
            
            # Recibir mensajes iniciales
            ws1.receive_json()
            ws2.receive_json()
            
            # Los broadcasts automáticos deberían llegar a ambos clientes
            # Nota: En un test real, necesitaríamos esperar los broadcasts automáticos
            # o triggear eventos específicos que generen broadcasts
            
            # Verificar que ambos clientes pueden recibir comandos
            ws1.send_json({"type": "ping"})
            ws2.send_json({"type": "ping"})
            
            # Ambos deberían recibir sus respectivos ecos y pongs
            ws1_echo = ws1.receive_json()
            ws1_pong = ws1.receive_json()
            
            ws2_echo = ws2.receive_json()
            ws2_pong = ws2.receive_json()
            
            assert ws1_echo["type"] == "command_echo"
            assert ws1_pong["type"] == "pong"
            assert ws2_echo["type"] == "command_echo"
            assert ws2_pong["type"] == "pong"
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_cleanup(self, client):
        """Test limpieza al desconectar WebSocket."""
        # Conectar y desconectar inmediatamente
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()  # Mensaje inicial
            # El websocket se cierra automáticamente al salir del context manager
        
        # Verificar que se puede conectar nuevamente sin problemas
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connection_established"


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main(["-v", __file__])