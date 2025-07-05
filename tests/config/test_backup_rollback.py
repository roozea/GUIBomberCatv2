"""Tests para backup y rollback de configuración BomberCat.

Este módulo contiene pruebas unitarias para las funcionalidades
de backup y rollback usando mocks para simular comunicación serie.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import time

import serial

from modules.bombercat_config.backup import (
    ConfigBackupManager, BackupError, RollbackError,
    backup_config, rollback, get_latest_backup, cleanup_old_backups
)


class TestConfigBackupManager:
    """Tests para ConfigBackupManager."""
    
    @pytest.fixture
    def temp_backup_dir(self):
        """Crear directorio temporal para backups."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def backup_manager(self, temp_backup_dir):
        """Crear instancia de ConfigBackupManager con directorio temporal."""
        return ConfigBackupManager(backup_dir=temp_backup_dir)
    
    @pytest.fixture
    def mock_serial_port(self):
        """Crear mock de puerto serie."""
        mock_port = Mock(spec=serial.Serial)
        mock_port.reset_input_buffer = Mock()
        mock_port.write = Mock()
        mock_port.flush = Mock()
        mock_port.in_waiting = 0
        mock_port.read = Mock()
        return mock_port
    
    def test_send_command_success(self, backup_manager, mock_serial_port):
        """Test envío exitoso de comando."""
        # Configurar respuesta JSON válida
        response_json = '{"status":"OK","data":{"mode":"client"}}'
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in response_json + '\n']
        mock_serial_port.in_waiting = 1
        
        result = backup_manager._send_command(mock_serial_port, "GET_CONFIG")
        
        assert result["status"] == "OK"
        assert result["data"]["mode"] == "client"
        mock_serial_port.write.assert_called_once()
        mock_serial_port.flush.assert_called_once()
    
    def test_send_command_timeout(self, backup_manager, mock_serial_port):
        """Test timeout en envío de comando."""
        # Simular que no hay datos disponibles
        mock_serial_port.in_waiting = 0
        
        with pytest.raises(BackupError) as exc_info:
            backup_manager._send_command(mock_serial_port, "GET_CONFIG", timeout=0.1)
        
        assert "Timeout" in str(exc_info.value)
    
    def test_send_command_invalid_json(self, backup_manager, mock_serial_port):
        """Test respuesta JSON inválida."""
        # Configurar respuesta no JSON
        invalid_response = "invalid json response"
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in invalid_response + '\n']
        mock_serial_port.in_waiting = 1
        
        with pytest.raises(BackupError) as exc_info:
            backup_manager._send_command(mock_serial_port, "GET_CONFIG")
        
        assert "no es JSON válido" in str(exc_info.value)
    
    def test_send_command_serial_exception(self, backup_manager, mock_serial_port):
        """Test excepción de comunicación serie."""
        mock_serial_port.write.side_effect = serial.SerialException("Puerto cerrado")
        
        with pytest.raises(BackupError) as exc_info:
            backup_manager._send_command(mock_serial_port, "GET_CONFIG")
        
        assert "Error de comunicación serie" in str(exc_info.value)
    
    def test_backup_config_success(self, backup_manager, mock_serial_port):
        """Test backup exitoso de configuración."""
        # Configurar respuesta exitosa
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        response_json = json.dumps({
            "status": "OK",
            "data": config_data
        })
        
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in response_json + '\n']
        mock_serial_port.in_waiting = 1
        
        result = backup_manager.backup_config(mock_serial_port)
        
        assert result == config_data
        mock_serial_port.write.assert_called_with(b"GET_CONFIG\n")
    
    def test_backup_config_device_error(self, backup_manager, mock_serial_port):
        """Test error del dispositivo durante backup."""
        # Configurar respuesta de error del dispositivo
        response_json = json.dumps({
            "status": "ERR",
            "msg": "NVS corrupted"
        })
        
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in response_json + '\n']
        mock_serial_port.in_waiting = 1
        
        with pytest.raises(BackupError) as exc_info:
            backup_manager.backup_config(mock_serial_port)
        
        assert "NVS corrupted" in str(exc_info.value)
    
    def test_backup_config_no_data(self, backup_manager, mock_serial_port):
        """Test backup sin datos de configuración."""
        # Configurar respuesta sin datos
        response_json = json.dumps({
            "status": "OK",
            "data": {}
        })
        
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in response_json + '\n']
        mock_serial_port.in_waiting = 1
        
        with pytest.raises(BackupError) as exc_info:
            backup_manager.backup_config(mock_serial_port)
        
        assert "no contiene datos" in str(exc_info.value)
    
    def test_backup_config_invalid_data(self, backup_manager, mock_serial_port):
        """Test backup con datos inválidos (pero se permite)."""
        # Configurar respuesta con datos inválidos
        invalid_config = {
            "mode": "invalid_mode",
            "wifi_ssid": "",
            "wifi_password": "123",
            "encryption_key": "invalid"
        }
        
        response_json = json.dumps({
            "status": "OK",
            "data": invalid_config
        })
        
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in response_json + '\n']
        mock_serial_port.in_waiting = 1
        
        # Debe retornar datos sin validar para permitir rollback
        result = backup_manager.backup_config(mock_serial_port)
        assert result == invalid_config
    
    def test_rollback_success(self, backup_manager, mock_serial_port):
        """Test rollback exitoso."""
        backup_config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Configurar respuestas para rollback y verificación
        responses = [
            # Respuesta del SET_CONFIG
            json.dumps({"status": "OK"}) + '\n',
            # Respuesta del GET_CONFIG para verificación
            json.dumps({
                "status": "OK",
                "data": backup_config_data
            }) + '\n'
        ]
        
        def mock_read_side_effect():
            response = responses.pop(0)
            for char in response:
                yield char.encode('utf-8')
        
        mock_serial_port.read.side_effect = []
        call_count = 0
        
        def mock_read(*args):
            nonlocal call_count
            if call_count < len(responses[0]):
                char = responses[0][call_count]
                call_count += 1
                if call_count >= len(responses[0]):
                    responses.pop(0)
                    call_count = 0
                return char.encode('utf-8')
            return b''
        
        # Simular respuestas secuenciales
        response_chars = []
        for response in responses:
            response_chars.extend([c.encode('utf-8') for c in response])
        
        mock_serial_port.read.side_effect = response_chars
        mock_serial_port.in_waiting = 1
        
        result = backup_manager.rollback(mock_serial_port, backup_config_data)
        
        assert result is True
        assert mock_serial_port.write.call_count >= 1
    
    def test_rollback_device_error(self, backup_manager, mock_serial_port):
        """Test error del dispositivo durante rollback."""
        backup_config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Configurar respuesta de error
        response_json = json.dumps({
            "status": "ERR",
            "msg": "Invalid configuration"
        })
        
        mock_serial_port.read.side_effect = [c.encode('utf-8') for c in response_json + '\n']
        mock_serial_port.in_waiting = 1
        
        with pytest.raises(RollbackError) as exc_info:
            backup_manager.rollback(mock_serial_port, backup_config_data)
        
        assert "Invalid configuration" in str(exc_info.value)
    
    def test_configs_match(self, backup_manager):
        """Test comparación de configuraciones."""
        config1 = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        config2 = config1.copy()
        assert backup_manager._configs_match(config1, config2) is True
        
        # Cambiar un campo
        config2["mode"] = "host"
        assert backup_manager._configs_match(config1, config2) is False
        
        # Agregar campo extra (no debería afectar)
        config2["mode"] = "client"
        config2["extra_field"] = "extra_value"
        assert backup_manager._configs_match(config1, config2) is True
    
    def test_save_local_backup(self, backup_manager, temp_backup_dir):
        """Test guardado de backup local."""
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        backup_file = backup_manager._save_local_backup(config_data)
        
        assert backup_file.exists()
        assert backup_file.name.startswith("config_backup_")
        assert backup_file.suffix == ".json"
        
        # Verificar contenido
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        assert "timestamp" in backup_data
        assert backup_data["config"] == config_data
    
    def test_get_latest_backup(self, backup_manager, temp_backup_dir):
        """Test obtención del backup más reciente."""
        # Sin backups
        assert backup_manager.get_latest_backup() is None
        
        # Crear varios backups
        config1 = {"mode": "client", "wifi_ssid": "Network1", "wifi_password": "pass1", "encryption_key": "A" * 32}
        config2 = {"mode": "host", "wifi_ssid": "Network2", "wifi_password": "pass2", "encryption_key": "B" * 32}
        
        backup_manager._save_local_backup(config1)
        time.sleep(0.01)  # Asegurar diferentes timestamps
        backup_manager._save_local_backup(config2)
        
        latest = backup_manager.get_latest_backup()
        assert latest == config2
    
    def test_cleanup_old_backups(self, backup_manager, temp_backup_dir):
        """Test limpieza de backups antiguos."""
        # Crear múltiples backups
        configs = [
            {"mode": "client", "wifi_ssid": f"Network{i}", "wifi_password": f"pass{i}", "encryption_key": "A" * 32}
            for i in range(5)
        ]
        
        for config in configs:
            backup_manager._save_local_backup(config)
            time.sleep(0.01)
        
        # Verificar que se crearon 5 backups
        backup_files = list(temp_backup_dir.glob("config_backup_*.json"))
        assert len(backup_files) == 5
        
        # Limpiar manteniendo solo 3
        deleted_count = backup_manager.cleanup_old_backups(keep_count=3)
        
        assert deleted_count == 2
        
        # Verificar que quedan solo 3
        remaining_files = list(temp_backup_dir.glob("config_backup_*.json"))
        assert len(remaining_files) == 3
    
    def test_cleanup_no_backups_to_delete(self, backup_manager, temp_backup_dir):
        """Test limpieza cuando no hay backups que eliminar."""
        # Crear solo 2 backups
        for i in range(2):
            config = {"mode": "client", "wifi_ssid": f"Network{i}", "wifi_password": f"pass{i}", "encryption_key": "A" * 32}
            backup_manager._save_local_backup(config)
        
        # Intentar mantener 5 (más de los que hay)
        deleted_count = backup_manager.cleanup_old_backups(keep_count=5)
        
        assert deleted_count == 0
        
        # Verificar que siguen existiendo los 2
        remaining_files = list(temp_backup_dir.glob("config_backup_*.json"))
        assert len(remaining_files) == 2


class TestConvenienceFunctions:
    """Tests para funciones de conveniencia."""
    
    @pytest.fixture
    def mock_serial_port(self):
        """Crear mock de puerto serie."""
        mock_port = Mock(spec=serial.Serial)
        mock_port.reset_input_buffer = Mock()
        mock_port.write = Mock()
        mock_port.flush = Mock()
        mock_port.in_waiting = 1
        mock_port.read = Mock()
        return mock_port
    
    @patch('modules.bombercat_config.backup._backup_manager')
    def test_backup_config_function(self, mock_manager, mock_serial_port):
        """Test función de conveniencia backup_config."""
        expected_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        mock_manager.backup_config.return_value = expected_config
        
        result = backup_config(mock_serial_port)
        
        assert result == expected_config
        mock_manager.backup_config.assert_called_once_with(mock_serial_port)
    
    @patch('modules.bombercat_config.backup._backup_manager')
    def test_rollback_function(self, mock_manager, mock_serial_port):
        """Test función de conveniencia rollback."""
        backup_config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        mock_manager.rollback.return_value = True
        
        result = rollback(mock_serial_port, backup_config_data)
        
        assert result is True
        mock_manager.rollback.assert_called_once_with(mock_serial_port, backup_config_data)
    
    @patch('modules.bombercat_config.backup._backup_manager')
    def test_get_latest_backup_function(self, mock_manager):
        """Test función de conveniencia get_latest_backup."""
        expected_backup = {
            "mode": "host",
            "wifi_ssid": "LatestNetwork",
            "wifi_password": "latestpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        mock_manager.get_latest_backup.return_value = expected_backup
        
        result = get_latest_backup()
        
        assert result == expected_backup
        mock_manager.get_latest_backup.assert_called_once()
    
    @patch('modules.bombercat_config.backup._backup_manager')
    def test_cleanup_old_backups_function(self, mock_manager):
        """Test función de conveniencia cleanup_old_backups."""
        mock_manager.cleanup_old_backups.return_value = 3
        
        result = cleanup_old_backups(keep_count=5)
        
        assert result == 3
        mock_manager.cleanup_old_backups.assert_called_once_with(5)


class TestRetryMechanism:
    """Tests para mecanismo de reintentos."""
    
    @pytest.fixture
    def backup_manager(self):
        """Crear instancia de ConfigBackupManager."""
        return ConfigBackupManager()
    
    @pytest.fixture
    def mock_serial_port(self):
        """Crear mock de puerto serie."""
        mock_port = Mock(spec=serial.Serial)
        mock_port.reset_input_buffer = Mock()
        mock_port.write = Mock()
        mock_port.flush = Mock()
        mock_port.in_waiting = 1
        mock_port.read = Mock()
        return mock_port
    
    def test_backup_retry_success_after_failure(self, backup_manager, mock_serial_port):
        """Test éxito después de fallos con reintentos."""
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Primer intento falla, segundo éxito
        responses = [
            # Primer intento - falla
            serial.SerialException("Connection lost"),
            # Segundo intento - éxito
            json.dumps({"status": "OK", "data": config_data}) + '\n'
        ]
        
        call_count = 0
        def mock_send_command_side_effect(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                raise responses[0]
            else:
                # Simular respuesta exitosa
                return {"status": "OK", "data": config_data}
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_side_effect):
            result = backup_manager.backup_config(mock_serial_port)
            assert result == config_data
    
    def test_rollback_retry_success_after_failure(self, backup_manager, mock_serial_port):
        """Test rollback con éxito después de fallos."""
        backup_config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "password123",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        call_count = 0
        def mock_send_command_side_effect(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                raise serial.SerialException("Temporary failure")
            else:
                # Simular respuesta exitosa
                return {"status": "OK"}
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_side_effect):
            # Mock del backup para verificación
            with patch.object(backup_manager, 'backup_config', return_value=backup_config_data):
                result = backup_manager.rollback(mock_serial_port, backup_config_data)
                assert result is True
    
    def test_backup_max_retries_exceeded(self, backup_manager, mock_serial_port):
        """Test fallo después de exceder máximo de reintentos."""
        # Configurar para que siempre falle
        with patch.object(backup_manager, '_send_command', side_effect=serial.SerialException("Persistent failure")):
            with pytest.raises(BackupError):
                backup_manager.backup_config(mock_serial_port)