"""Context manager para transacciones de configuración BomberCat.

Este módulo proporciona un context manager que garantiza backup automático
y rollback en caso de fallos durante la aplicación de configuraciones.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, AsyncContextManager
from contextlib import asynccontextmanager

import serial
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from modules.bombercat_config.backup import ConfigBackupManager, BackupError, RollbackError
from modules.bombercat_config.validators import ConfigValidator, BomberCatConfig


logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Error durante transacción de configuración."""
    pass


class ConfigTransaction:
    """Context manager para transacciones de configuración.
    
    Garantiza backup automático al entrar y rollback automático
    en caso de excepción durante la transacción.
    
    Ejemplo de uso:
        async with ConfigTransaction(port) as tx:
            await tx.send(config_dict)
    """
    
    def __init__(self, port: serial.Serial, 
                 backup_manager: Optional[ConfigBackupManager] = None,
                 auto_rollback: bool = True,
                 timeout: float = 30.0):
        """Inicializar transacción de configuración.
        
        Args:
            port: Puerto serie conectado al dispositivo
            backup_manager: Gestor de backup personalizado
            auto_rollback: Si hacer rollback automático en caso de error
            timeout: Timeout para operaciones de configuración
        """
        self.port = port
        self.backup_manager = backup_manager or ConfigBackupManager()
        self.auto_rollback = auto_rollback
        self.timeout = timeout
        
        # Estado de la transacción
        self._backup_config: Optional[Dict[str, Any]] = None
        self._transaction_started = False
        self._config_applied = False
        self._rollback_performed = False
    
    async def __aenter__(self) -> 'ConfigTransaction':
        """Entrar al context manager.
        
        Returns:
            ConfigTransaction: Instancia de la transacción
            
        Raises:
            TransactionError: Si no se puede iniciar la transacción
        """
        try:
            logger.info("Iniciando transacción de configuración")
            
            # Hacer backup de la configuración actual
            self._backup_config = await self._async_backup()
            self._transaction_started = True
            
            logger.info("Transacción iniciada exitosamente")
            return self
            
        except Exception as e:
            logger.error(f"Error iniciando transacción: {e}")
            raise TransactionError(f"No se pudo iniciar transacción: {e}") from e
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Salir del context manager.
        
        Args:
            exc_type: Tipo de excepción si ocurrió
            exc_val: Valor de excepción si ocurrió
            exc_tb: Traceback de excepción si ocurrió
        """
        try:
            if exc_type is not None:
                # Hubo una excepción, realizar rollback si está habilitado
                logger.warning(f"Excepción en transacción: {exc_type.__name__}: {exc_val}")
                
                if self.auto_rollback and self._backup_config and not self._rollback_performed:
                    try:
                        await self._async_rollback()
                        logger.info("Rollback automático completado")
                    except Exception as rollback_error:
                        logger.error(f"Error durante rollback automático: {rollback_error}")
                        # No suprimir la excepción original
            else:
                # Transacción exitosa
                if self._config_applied:
                    logger.info("Transacción completada exitosamente")
                else:
                    logger.warning("Transacción completada sin aplicar configuración")
            
        except Exception as e:
            logger.error(f"Error durante salida de transacción: {e}")
        
        finally:
            self._transaction_started = False
    
    async def send(self, config_data: Dict[str, Any], 
                  validate: bool = True) -> Dict[str, Any]:
        """Enviar configuración al dispositivo.
        
        Args:
            config_data: Datos de configuración a enviar
            validate: Si validar la configuración antes de enviar
            
        Returns:
            dict: Respuesta del dispositivo
            
        Raises:
            TransactionError: Si no se puede enviar la configuración
        """
        if not self._transaction_started:
            raise TransactionError("Transacción no iniciada")
        
        try:
            logger.info("Enviando configuración al dispositivo")
            
            # Validar configuración si se solicita
            if validate:
                validated_config = ConfigValidator.validate_config(config_data)
                config_to_send = validated_config.model_dump()
            else:
                config_to_send = config_data
            
            # Enviar configuración
            response = await self._async_send_config(config_to_send)
            
            # Verificar respuesta
            if response.get("status") != "OK":
                error_msg = response.get("msg", "Error desconocido")
                raise TransactionError(f"Error aplicando configuración: {error_msg}")
            
            self._config_applied = True
            logger.info("Configuración aplicada exitosamente")
            
            return response
            
        except Exception as e:
            logger.error(f"Error enviando configuración: {e}")
            raise TransactionError(f"No se pudo enviar configuración: {e}") from e
    
    async def verify(self) -> bool:
        """Verificar que la configuración se aplicó correctamente.
        
        Returns:
            bool: True si la verificación es exitosa
            
        Raises:
            TransactionError: Si la verificación falla
        """
        if not self._transaction_started:
            raise TransactionError("Transacción no iniciada")
        
        try:
            logger.info("Verificando configuración aplicada")
            
            # Enviar comando de verificación
            response = await self._async_send_command("VERIFY_CONFIG")
            
            # Verificar respuesta
            if response.get("status") != "OK":
                error_msg = response.get("msg", "Verificación falló")
                raise TransactionError(f"Verificación falló: {error_msg}")
            
            logger.info("Verificación exitosa")
            return True
            
        except Exception as e:
            logger.error(f"Error durante verificación: {e}")
            raise TransactionError(f"No se pudo verificar configuración: {e}") from e
    
    async def rollback(self) -> bool:
        """Realizar rollback manual a la configuración de backup.
        
        Returns:
            bool: True si el rollback fue exitoso
            
        Raises:
            TransactionError: Si el rollback falla
        """
        if not self._backup_config:
            raise TransactionError("No hay configuración de backup disponible")
        
        return await self._async_rollback()
    
    async def _async_backup(self) -> Dict[str, Any]:
        """Realizar backup de forma asíncrona.
        
        Returns:
            dict: Configuración de backup
        """
        import asyncio
        
        def _backup():
            return self.backup_manager.backup_config(self.port)
        
        # Ejecutar backup en thread pool para no bloquear
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _backup)
    
    async def _async_rollback(self) -> bool:
        """Realizar rollback de forma asíncrona.
        
        Returns:
            bool: True si el rollback fue exitoso
        """
        import asyncio
        
        if not self._backup_config:
            raise TransactionError("No hay configuración de backup")
        
        def _rollback():
            return self.backup_manager.rollback(self.port, self._backup_config)
        
        # Ejecutar rollback en thread pool para no bloquear
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _rollback)
        self._rollback_performed = True
        return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((serial.SerialException, TransactionError))
    )
    async def _async_send_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enviar configuración de forma asíncrona con reintentos.
        
        Args:
            config_data: Datos de configuración
            
        Returns:
            dict: Respuesta del dispositivo
        """
        import asyncio
        
        def _send_config():
            # Preparar comando
            config_command = {
                "command": "SET_CONFIG",
                "data": config_data
            }
            
            command_json = json.dumps(config_command, separators=(',', ':'))
            return self.backup_manager._send_command(self.port, command_json, self.timeout)
        
        # Ejecutar en thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_config)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((serial.SerialException, TransactionError))
    )
    async def _async_send_command(self, command: str) -> Dict[str, Any]:
        """Enviar comando de forma asíncrona con reintentos.
        
        Args:
            command: Comando a enviar
            
        Returns:
            dict: Respuesta del dispositivo
        """
        import asyncio
        
        def _send_command():
            return self.backup_manager._send_command(self.port, command, self.timeout)
        
        # Ejecutar en thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_command)
    
    @property
    def backup_config(self) -> Optional[Dict[str, Any]]:
        """Obtener configuración de backup.
        
        Returns:
            dict: Configuración de backup, None si no hay
        """
        return self._backup_config.copy() if self._backup_config else None
    
    @property
    def is_active(self) -> bool:
        """Verificar si la transacción está activa.
        
        Returns:
            bool: True si la transacción está activa
        """
        return self._transaction_started
    
    @property
    def config_applied(self) -> bool:
        """Verificar si se aplicó configuración.
        
        Returns:
            bool: True si se aplicó configuración
        """
        return self._config_applied
    
    @property
    def rollback_performed(self) -> bool:
        """Verificar si se realizó rollback.
        
        Returns:
            bool: True si se realizó rollback
        """
        return self._rollback_performed


# Context manager simplificado para casos básicos
@asynccontextmanager
async def config_transaction(port: serial.Serial, 
                           auto_rollback: bool = True,
                           timeout: float = 30.0) -> AsyncContextManager[ConfigTransaction]:
    """Context manager simplificado para transacciones de configuración.
    
    Args:
        port: Puerto serie conectado al dispositivo
        auto_rollback: Si hacer rollback automático en caso de error
        timeout: Timeout para operaciones
        
    Yields:
        ConfigTransaction: Instancia de transacción
        
    Ejemplo:
        async with config_transaction(port) as tx:
            await tx.send({"mode": "client", ...})
            await tx.verify()
    """
    transaction = ConfigTransaction(port, auto_rollback=auto_rollback, timeout=timeout)
    
    async with transaction as tx:
        yield tx


# Función de conveniencia para transacciones simples
async def apply_config_with_transaction(port: serial.Serial,
                                      config_data: Dict[str, Any],
                                      validate: bool = True,
                                      verify: bool = True,
                                      timeout: float = 30.0) -> Dict[str, Any]:
    """Aplicar configuración usando transacción automática.
    
    Args:
        port: Puerto serie conectado al dispositivo
        config_data: Datos de configuración
        validate: Si validar configuración antes de enviar
        verify: Si verificar configuración después de aplicar
        timeout: Timeout para operaciones
        
    Returns:
        dict: Respuesta del dispositivo
        
    Raises:
        TransactionError: Si la operación falla
    """
    async with config_transaction(port, timeout=timeout) as tx:
        response = await tx.send(config_data, validate=validate)
        
        if verify:
            await tx.verify()
        
        return response