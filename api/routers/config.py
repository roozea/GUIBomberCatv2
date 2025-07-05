"""Router para configuración de dispositivos BomberCat.

Este módulo proporciona endpoints FastAPI para configurar dinámicamente
dispositivos BomberCat incluyendo modo, Wi-Fi y claves de encriptación.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import serial
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from modules.bombercat_config.validators import ConfigValidator, BomberCatConfig
from modules.bombercat_config.backup import (
    ConfigBackupManager, BackupError, RollbackError
)
from modules.bombercat_config.transaction import (
    ConfigTransaction, TransactionError, apply_config_with_transaction
)
from api.dependencies import get_serial_port


logger = logging.getLogger(__name__)

# Router de configuración
router = APIRouter(
    prefix="/config",
    tags=["configuration"],
    responses={
        404: {"description": "Dispositivo no encontrado"},
        400: {"description": "Error de validación o configuración"},
        500: {"description": "Error interno del servidor"}
    }
)

# Gestor de backup global
backup_manager = ConfigBackupManager()


class ConfigRequest(BaseModel):
    """Modelo para solicitudes de configuración."""
    
    mode: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    encryption_key: Optional[str] = None
    
    # Opciones de aplicación
    validate: bool = True
    verify: bool = True
    timeout: float = 30.0
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "mode": "client",
                "wifi_ssid": "BomberCat_Network",
                "wifi_password": "SecurePassword123",
                "encryption_key": "0123456789ABCDEF0123456789ABCDEF",
                "validate": True,
                "verify": True,
                "timeout": 30.0
            }
        }
    }


class ConfigResponse(BaseModel):
    """Modelo para respuestas de configuración."""
    
    status: str
    message: str
    timestamp: datetime
    config_applied: Optional[Dict[str, Any]] = None
    backup_created: bool = False
    verification_passed: bool = False
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "message": "Configuración aplicada exitosamente",
                "timestamp": "2024-01-15T10:30:00",
                "config_applied": {
                    "mode": "client",
                    "wifi_ssid": "BomberCat_Network"
                },
                "backup_created": True,
                "verification_passed": True
            }
        }
    }


class StatusResponse(BaseModel):
    """Modelo para respuestas de estado."""
    
    status: str
    current_config: Optional[Dict[str, Any]] = None
    nvs_status: str
    device_connected: bool
    last_update: Optional[datetime] = None
    backup_available: bool = False
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "current_config": {
                    "mode": "client",
                    "wifi_ssid": "BomberCat_Network",
                    "wifi_password": "***",
                    "encryption_key": "***"
                },
                "nvs_status": "healthy",
                "device_connected": True,
                "last_update": "2024-01-15T10:30:00",
                "backup_available": True
            }
        }
    }


class VerifyResponse(BaseModel):
    """Modelo para respuestas de verificación."""
    
    status: str
    verification_passed: bool
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "verification_passed": True,
                "message": "Configuración verificada exitosamente",
                "timestamp": "2024-01-15T10:30:00",
                "details": {
                    "nvs_integrity": "ok",
                    "config_consistency": "ok"
                }
            }
        }
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((serial.SerialException, ConnectionError))
)
def send_command_with_retry(port: serial.Serial, command: str, 
                          timeout: float = 5.0) -> Dict[str, Any]:
    """Enviar comando al dispositivo con reintentos automáticos.
    
    Args:
        port: Puerto serie conectado al dispositivo
        command: Comando a enviar
        timeout: Timeout para la respuesta
        
    Returns:
        dict: Respuesta del dispositivo parseada como JSON
        
    Raises:
        HTTPException: Si la comunicación falla después de reintentos
    """
    try:
        return backup_manager._send_command(port, command, timeout)
    except Exception as e:
        logger.error(f"Error enviando comando después de reintentos: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error de comunicación con dispositivo: {e}"
        )


@router.post("/", response_model=ConfigResponse)
async def apply_config(
    config_request: ConfigRequest,
    port: serial.Serial = Depends(get_serial_port)
) -> ConfigResponse:
    """Aplicar nueva configuración al dispositivo BomberCat.
    
    Este endpoint aplica una nueva configuración al dispositivo usando
    transacciones con backup automático y rollback en caso de fallo.
    
    Args:
        config_request: Datos de configuración a aplicar
        port: Puerto serie del dispositivo
        
    Returns:
        ConfigResponse: Resultado de la operación
        
    Raises:
        HTTPException: Si la configuración falla
    """
    start_time = datetime.now()
    
    try:
        logger.info("Iniciando aplicación de configuración")
        
        # Filtrar campos no nulos para configuración parcial
        config_data = {
            k: v for k, v in config_request.model_dump().items() 
            if v is not None and k not in ['validate', 'verify', 'timeout']
        }
        
        if not config_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se proporcionaron datos de configuración"
            )
        
        # Obtener configuración actual para merge si es parcial
        try:
            current_config = backup_manager.backup_config(port)
            if len(config_data) < 4:  # Configuración parcial
                merged_config = current_config.copy()
                merged_config.update(config_data)
                config_data = merged_config
        except BackupError:
            # Si no se puede obtener config actual, usar solo la nueva
            logger.warning("No se pudo obtener configuración actual, usando solo nueva")
        
        # Aplicar configuración usando transacción
        try:
            response = await apply_config_with_transaction(
                port=port,
                config_data=config_data,
                validate=config_request.validate,
                verify=config_request.verify,
                timeout=config_request.timeout
            )
            
            return ConfigResponse(
                status="success",
                message="Configuración aplicada exitosamente",
                timestamp=start_time,
                config_applied=config_data,
                backup_created=True,
                verification_passed=config_request.verify
            )
            
        except ValidationError as e:
            logger.error(f"Error de validación: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error de validación: {e}"
            )
        
        except TransactionError as e:
            logger.error(f"Error en transacción: {e}")
            
            # Verificar si el error indica NACK del dispositivo
            if "Error aplicando configuración" in str(e):
                # Extraer mensaje de error del dispositivo
                error_msg = str(e).split(":", 1)[-1].strip()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dispositivo rechazó configuración: {error_msg}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error interno aplicando configuración: {e}"
                )
        
    except HTTPException:
        # Re-lanzar HTTPExceptions tal como están
        raise
    
    except Exception as e:
        logger.error(f"Error inesperado aplicando configuración: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {e}"
        )


@router.get("/status", response_model=StatusResponse)
async def get_config_status(
    port: serial.Serial = Depends(get_serial_port)
) -> StatusResponse:
    """Obtener estado actual de configuración del dispositivo.
    
    Args:
        port: Puerto serie del dispositivo
        
    Returns:
        StatusResponse: Estado actual del dispositivo
        
    Raises:
        HTTPException: Si no se puede obtener el estado
    """
    try:
        logger.info("Obteniendo estado de configuración")
        
        # Verificar conexión del dispositivo
        try:
            # Enviar comando de ping para verificar conexión
            ping_response = send_command_with_retry(port, "PING", timeout=3.0)
            device_connected = ping_response.get("status") == "OK"
        except Exception:
            device_connected = False
        
        if not device_connected:
            return StatusResponse(
                status="disconnected",
                current_config=None,
                nvs_status="unknown",
                device_connected=False,
                backup_available=backup_manager.get_latest_backup() is not None
            )
        
        # Obtener configuración actual
        try:
            current_config = backup_manager.backup_config(port)
            
            # Ocultar información sensible
            safe_config = current_config.copy()
            if "wifi_password" in safe_config:
                safe_config["wifi_password"] = "***"
            if "encryption_key" in safe_config:
                safe_config["encryption_key"] = "***"
            
        except BackupError as e:
            logger.warning(f"No se pudo obtener configuración actual: {e}")
            current_config = None
            safe_config = None
        
        # Obtener estado de NVS
        try:
            nvs_response = send_command_with_retry(port, "GET_NVS_STATUS", timeout=5.0)
            nvs_status = nvs_response.get("nvs_status", "unknown")
        except Exception:
            nvs_status = "unknown"
        
        return StatusResponse(
            status="ok" if current_config else "partial",
            current_config=safe_config,
            nvs_status=nvs_status,
            device_connected=device_connected,
            last_update=datetime.now(),
            backup_available=backup_manager.get_latest_backup() is not None
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado del dispositivo: {e}"
        )


@router.post("/verify", response_model=VerifyResponse)
async def verify_config(
    port: serial.Serial = Depends(get_serial_port)
) -> VerifyResponse:
    """Verificar integridad de la configuración actual.
    
    Args:
        port: Puerto serie del dispositivo
        
    Returns:
        VerifyResponse: Resultado de la verificación
        
    Raises:
        HTTPException: Si la verificación falla
    """
    timestamp = datetime.now()
    
    try:
        logger.info("Iniciando verificación de configuración")
        
        # Enviar comando de verificación
        try:
            verify_response = send_command_with_retry(port, "VERIFY_CONFIG", timeout=10.0)
            
            verification_passed = verify_response.get("status") == "OK"
            details = verify_response.get("details", {})
            
            if verification_passed:
                message = "Configuración verificada exitosamente"
            else:
                error_msg = verify_response.get("msg", "Verificación falló")
                message = f"Verificación falló: {error_msg}"
            
            return VerifyResponse(
                status="success" if verification_passed else "failed",
                verification_passed=verification_passed,
                message=message,
                timestamp=timestamp,
                details=details
            )
            
        except Exception as e:
            logger.error(f"Error durante verificación: {e}")
            return VerifyResponse(
                status="error",
                verification_passed=False,
                message=f"Error durante verificación: {e}",
                timestamp=timestamp
            )
        
    except Exception as e:
        logger.error(f"Error inesperado durante verificación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno durante verificación: {e}"
        )


@router.post("/rollback", response_model=ConfigResponse)
async def rollback_config(
    port: serial.Serial = Depends(get_serial_port)
) -> ConfigResponse:
    """Realizar rollback a la última configuración válida.
    
    Args:
        port: Puerto serie del dispositivo
        
    Returns:
        ConfigResponse: Resultado del rollback
        
    Raises:
        HTTPException: Si el rollback falla
    """
    timestamp = datetime.now()
    
    try:
        logger.info("Iniciando rollback de configuración")
        
        # Obtener último backup
        backup_config = backup_manager.get_latest_backup()
        
        if not backup_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay configuración de backup disponible"
            )
        
        # Realizar rollback
        try:
            success = backup_manager.rollback(port, backup_config)
            
            if success:
                return ConfigResponse(
                    status="success",
                    message="Rollback completado exitosamente",
                    timestamp=timestamp,
                    config_applied=backup_config,
                    backup_created=False,
                    verification_passed=True
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Rollback falló por razones desconocidas"
                )
                
        except RollbackError as e:
            logger.error(f"Error durante rollback: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error durante rollback: {e}"
            )
        
    except HTTPException:
        # Re-lanzar HTTPExceptions tal como están
        raise
    
    except Exception as e:
        logger.error(f"Error inesperado durante rollback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno durante rollback: {e}"
        )


@router.delete("/backup")
async def cleanup_backups(keep_count: int = 10) -> JSONResponse:
    """Limpiar backups antiguos manteniendo solo los más recientes.
    
    Args:
        keep_count: Número de backups a mantener
        
    Returns:
        JSONResponse: Resultado de la limpieza
    """
    try:
        deleted_count = backup_manager.cleanup_old_backups(keep_count)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Limpieza completada. {deleted_count} backups eliminados",
                "deleted_count": deleted_count,
                "kept_count": keep_count
            }
        )
        
    except Exception as e:
        logger.error(f"Error durante limpieza de backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante limpieza: {e}"
        )


# Nota: Los exception handlers deben registrarse en la aplicación principal,
# no en el router. Ver api/main.py para los manejadores de errores globales.