"""Tests para protocolo de reintentos de configuración BomberCat.

Este módulo contiene pruebas para verificar el comportamiento
del protocolo de comunicación con reintentos automáticos.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
from concurrent.futures import ThreadPoolExecutor

import serial
from tenacity import RetryError

from modules.bombercat_config.transaction import (
    ConfigTransaction, TransactionError, config_transaction, apply_config_with_transaction
)
from modules.bombercat_config.backup import ConfigBackupManager, BackupError, RollbackError
from api.routers.config import send_command_with_retry


class TestSendCommandWithRetry:
    """Tests para función send_command_with_retry."""
    
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
    
    @patch('api.routers.config.backup_manager')
    def test_success_first_attempt(self, mock_backup_manager, mock_serial_port):
        """Test éxito en el primer intento."""
        expected_response = {"status": "OK", "data": {"mode": "client"}}
        mock_backup_manager._send_command.return_value = expected_response
        
        result = send_command_with_retry(mock_serial_port, "GET_CONFIG")
        
        assert result == expected_response
        mock_backup_manager._send_command.assert_called_once_with(
            mock_serial_port, "GET_CONFIG", 5.0
        )
    
    @patch('api.routers.config.backup_manager')
    def test_success_after_two_failures(self, mock_backup_manager, mock_serial_port):
        """Test éxito después de dos fallos."""
        expected_response = {"status": "OK", "data": {"mode": "client"}}
        
        # Configurar para fallar 2 veces, luego éxito
        mock_backup_manager._send_command.side_effect = [
            serial.SerialException("Fallo 1"),
            serial.SerialException("Fallo 2"),
            expected_response
        ]
        
        result = send_command_with_retry(mock_serial_port, "GET_CONFIG")
        
        assert result == expected_response
        assert mock_backup_manager._send_command.call_count == 3
    
    @patch('api.routers.config.backup_manager')
    def test_failure_after_max_retries(self, mock_backup_manager, mock_serial_port):
        """Test fallo después de máximo de reintentos."""
        # Configurar para fallar siempre
        mock_backup_manager._send_command.side_effect = serial.SerialException("Fallo persistente")
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            send_command_with_retry(mock_serial_port, "GET_CONFIG")
        
        assert exc_info.value.status_code == 503
        assert "Error de comunicación" in exc_info.value.detail
        assert mock_backup_manager._send_command.call_count == 3  # Máximo reintentos
    
    @patch('api.routers.config.backup_manager')
    def test_connection_error_retry(self, mock_backup_manager, mock_serial_port):
        """Test reintentos con ConnectionError."""
        expected_response = {"status": "OK"}
        
        # Configurar para fallar con ConnectionError, luego éxito
        mock_backup_manager._send_command.side_effect = [
            ConnectionError("Connection lost"),
            expected_response
        ]
        
        result = send_command_with_retry(mock_serial_port, "GET_CONFIG")
        
        assert result == expected_response
        assert mock_backup_manager._send_command.call_count == 2
    
    @patch('api.routers.config.backup_manager')
    def test_other_exception_no_retry(self, mock_backup_manager, mock_serial_port):
        """Test que otras excepciones no se reintentan."""
        # Configurar para fallar con excepción no reintentable
        mock_backup_manager._send_command.side_effect = ValueError("Invalid data")
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            send_command_with_retry(mock_serial_port, "GET_CONFIG")
        
        assert exc_info.value.status_code == 503
        # Solo debe intentar una vez para excepciones no reintentables
        assert mock_backup_manager._send_command.call_count == 1
    
    @patch('api.routers.config.backup_manager')
    def test_custom_timeout(self, mock_backup_manager, mock_serial_port):
        """Test con timeout personalizado."""
        expected_response = {"status": "OK"}
        mock_backup_manager._send_command.return_value = expected_response
        
        result = send_command_with_retry(mock_serial_port, "GET_CONFIG", timeout=10.0)
        
        assert result == expected_response
        mock_backup_manager._send_command.assert_called_once_with(
            mock_serial_port, "GET_CONFIG", 10.0
        )


class TestConfigTransactionRetry:
    """Tests para reintentos en ConfigTransaction."""
    
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
    
    @pytest.fixture
    def mock_backup_manager(self):
        """Crear mock de ConfigBackupManager."""
        mock_manager = Mock(spec=ConfigBackupManager)
        return mock_manager
    
    @pytest.mark.asyncio
    async def test_transaction_success_after_retry(self, mock_serial_port, mock_backup_manager):
        """Test transacción exitosa después de reintentos."""
        backup_config = {
            "mode": "client",
            "wifi_ssid": "OldNetwork",
            "wifi_password": "oldpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        new_config = {
            "mode": "host",
            "wifi_ssid": "NewNetwork",
            "wifi_password": "newpass",
            "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
        }
        
        # Configurar backup exitoso
        mock_backup_manager.backup_config.return_value = backup_config
        
        # Configurar envío de configuración con fallo inicial
        call_count = 0
        def mock_send_command_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise serial.SerialException("Temporary failure")
            else:
                return {"status": "OK"}
        
        mock_backup_manager._send_command.side_effect = mock_send_command_side_effect
        
        transaction = ConfigTransaction(mock_serial_port, mock_backup_manager)
        
        async with transaction as tx:
            response = await tx.send(new_config)
            assert response["status"] == "OK"
        
        # Verificar que se hicieron reintentos
        assert mock_backup_manager._send_command.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_after_max_retries(self, mock_serial_port, mock_backup_manager):
        """Test rollback después de exceder máximo de reintentos."""
        backup_config = {
            "mode": "client",
            "wifi_ssid": "OldNetwork",
            "wifi_password": "oldpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        new_config = {
            "mode": "host",
            "wifi_ssid": "NewNetwork",
            "wifi_password": "newpass",
            "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
        }
        
        # Configurar backup exitoso
        mock_backup_manager.backup_config.return_value = backup_config
        
        # Configurar para que siempre falle el envío
        mock_backup_manager._send_command.side_effect = serial.SerialException("Persistent failure")
        
        # Configurar rollback exitoso
        mock_backup_manager.rollback.return_value = True
        
        transaction = ConfigTransaction(mock_serial_port, mock_backup_manager)
        
        with pytest.raises(TransactionError):
            async with transaction as tx:
                await tx.send(new_config)
        
        # Verificar que se intentó rollback
        mock_backup_manager.rollback.assert_called_once_with(mock_serial_port, backup_config)
    
    @pytest.mark.asyncio
    async def test_verify_command_retry(self, mock_serial_port, mock_backup_manager):
        """Test reintentos en comando de verificación."""
        backup_config = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Configurar backup exitoso
        mock_backup_manager.backup_config.return_value = backup_config
        
        # Configurar respuestas para envío y verificación
        responses = [
            {"status": "OK"},  # Respuesta del SET_CONFIG
            serial.SerialException("Verify failure 1"),  # Primer intento de verificación falla
            {"status": "OK"}   # Segundo intento de verificación éxito
        ]
        
        mock_backup_manager._send_command.side_effect = responses
        
        transaction = ConfigTransaction(mock_serial_port, mock_backup_manager)
        
        async with transaction as tx:
            await tx.send(backup_config, validate=False)
            result = await tx.verify()
            assert result is True
        
        # Verificar que se hicieron los llamados esperados
        assert mock_backup_manager._send_command.call_count == 3


class TestApplyConfigWithTransactionRetry:
    """Tests para apply_config_with_transaction con reintentos."""
    
    @pytest.fixture
    def mock_serial_port(self):
        """Crear mock de puerto serie."""
        mock_port = Mock(spec=serial.Serial)
        return mock_port
    
    @pytest.mark.asyncio
    @patch('modules.bombercat_config.transaction.ConfigBackupManager')
    async def test_apply_config_success_after_backup_retry(self, mock_backup_manager_class, mock_serial_port):
        """Test aplicación exitosa después de reintentos en backup."""
        mock_backup_manager = Mock()
        mock_backup_manager_class.return_value = mock_backup_manager
        
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        backup_config = {
            "mode": "host",
            "wifi_ssid": "OldNetwork",
            "wifi_password": "oldpass",
            "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
        }
        
        # Configurar backup con fallo inicial
        backup_call_count = 0
        def mock_backup_side_effect(*args, **kwargs):
            nonlocal backup_call_count
            backup_call_count += 1
            if backup_call_count == 1:
                raise BackupError("Backup failure")
            else:
                return backup_config
        
        mock_backup_manager.backup_config.side_effect = mock_backup_side_effect
        
        # Configurar envío exitoso
        mock_backup_manager._send_command.return_value = {"status": "OK"}
        
        result = await apply_config_with_transaction(
            mock_serial_port, config_data, validate=False, verify=False
        )
        
        assert result["status"] == "OK"
        assert mock_backup_manager.backup_config.call_count == 2
    
    @pytest.mark.asyncio
    @patch('modules.bombercat_config.transaction.ConfigBackupManager')
    async def test_apply_config_failure_with_rollback_retry(self, mock_backup_manager_class, mock_serial_port):
        """Test fallo en aplicación con reintentos en rollback."""
        mock_backup_manager = Mock()
        mock_backup_manager_class.return_value = mock_backup_manager
        
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        backup_config = {
            "mode": "host",
            "wifi_ssid": "OldNetwork",
            "wifi_password": "oldpass",
            "encryption_key": "FEDCBA9876543210FEDCBA9876543210"
        }
        
        # Configurar backup exitoso
        mock_backup_manager.backup_config.return_value = backup_config
        
        # Configurar envío que falla
        mock_backup_manager._send_command.side_effect = [
            {"status": "ERR", "msg": "Invalid configuration"}  # Fallo en SET_CONFIG
        ]
        
        # Configurar rollback con fallo inicial
        rollback_call_count = 0
        def mock_rollback_side_effect(*args, **kwargs):
            nonlocal rollback_call_count
            rollback_call_count += 1
            if rollback_call_count == 1:
                raise RollbackError("Rollback failure")
            else:
                return True
        
        mock_backup_manager.rollback.side_effect = mock_rollback_side_effect
        
        with pytest.raises(TransactionError):
            await apply_config_with_transaction(
                mock_serial_port, config_data, validate=False, verify=False
            )
        
        # Verificar que se intentó rollback con reintentos
        assert mock_backup_manager.rollback.call_count == 2


class TestBackupManagerRetryMechanism:
    """Tests específicos para mecanismo de reintentos en ConfigBackupManager."""
    
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
    
    def test_backup_exponential_backoff(self, backup_manager, mock_serial_port):
        """Test que el backoff exponencial funciona correctamente."""
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Configurar para fallar 2 veces, luego éxito
        call_times = []
        
        def mock_send_command_side_effect(*args, **kwargs):
            import time
            call_times.append(time.time())
            
            if len(call_times) <= 2:
                raise serial.SerialException(f"Failure {len(call_times)}")
            else:
                return {"status": "OK", "data": config_data}
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_side_effect):
            result = backup_manager.backup_config(mock_serial_port)
            assert result == config_data
        
        # Verificar que hubo delays entre intentos
        assert len(call_times) == 3
        if len(call_times) >= 2:
            # Debe haber al menos 1 segundo de delay entre primer y segundo intento
            delay1 = call_times[1] - call_times[0]
            assert delay1 >= 0.9  # Permitir pequeña variación
        
        if len(call_times) >= 3:
            # El segundo delay debe ser mayor (backoff exponencial)
            delay2 = call_times[2] - call_times[1]
            assert delay2 >= delay1 * 0.9  # Permitir variación
    
    def test_rollback_retry_specific_exceptions(self, backup_manager, mock_serial_port):
        """Test que solo se reintentan excepciones específicas."""
        backup_config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        # Test con excepción reintentable
        call_count = 0
        def mock_send_command_reintentable(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise serial.SerialException("Reintentable")
            else:
                return {"status": "OK"}
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_reintentable):
            with patch.object(backup_manager, 'backup_config', return_value=backup_config_data):
                result = backup_manager.rollback(mock_serial_port, backup_config_data)
                assert result is True
                assert call_count == 3
        
        # Test con excepción no reintentable
        call_count = 0
        def mock_send_command_no_reintentable(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError("No reintentable")
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_no_reintentable):
            with pytest.raises(RollbackError):
                backup_manager.rollback(mock_serial_port, backup_config_data)
            # Solo debe intentar una vez para excepciones no reintentables
            assert call_count == 1
    
    def test_max_retry_attempts(self, backup_manager, mock_serial_port):
        """Test que se respeta el máximo de intentos."""
        call_count = 0
        def mock_send_command_always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise serial.SerialException(f"Persistent failure {call_count}")
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_always_fail):
            with pytest.raises(BackupError):
                backup_manager.backup_config(mock_serial_port)
            
            # Debe intentar exactamente 3 veces (configuración de tenacity)
            assert call_count == 3
    
    def test_retry_with_different_timeouts(self, backup_manager, mock_serial_port):
        """Test reintentos con diferentes timeouts."""
        config_data = {
            "mode": "client",
            "wifi_ssid": "TestNetwork",
            "wifi_password": "testpass",
            "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
        }
        
        timeouts_used = []
        
        def mock_send_command_track_timeout(*args, **kwargs):
            timeout = kwargs.get('timeout', args[2] if len(args) > 2 else 5.0)
            timeouts_used.append(timeout)
            
            if len(timeouts_used) <= 2:
                raise serial.SerialException("Timeout test")
            else:
                return {"status": "OK", "data": config_data}
        
        with patch.object(backup_manager, '_send_command', side_effect=mock_send_command_track_timeout):
            result = backup_manager.backup_config(mock_serial_port)
            assert result == config_data
        
        # Verificar que se usó el mismo timeout en todos los intentos
        assert len(timeouts_used) == 3
        assert all(timeout == timeouts_used[0] for timeout in timeouts_used)