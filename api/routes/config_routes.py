"""Configuration service API routes.

Endpoints para gestión de configuraciones de dispositivos.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from api.dependencies import get_config_service
from adapters.interfaces import ConfigServiceInterface


router = APIRouter()


class ConfigRequest(BaseModel):
    """Request model para operaciones de configuración."""
    device_id: str
    config_data: Dict[str, Any]
    backup: Optional[bool] = True


class ConfigResponse(BaseModel):
    """Response model para configuraciones."""
    device_id: str
    config_data: Dict[str, Any]
    timestamp: str
    version: Optional[str] = None


class BackupInfo(BaseModel):
    """Information about configuration backups."""
    device_id: str
    backup_id: str
    timestamp: str
    description: Optional[str] = None


@router.get("/devices", response_model=List[str])
async def list_configured_devices(
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> List[str]:
    """Lista dispositivos con configuración."""
    try:
        devices = await config_service.list_devices()
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing devices: {str(e)}")


@router.get("/device/{device_id}", response_model=ConfigResponse)
async def get_device_config(
    device_id: str,
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> ConfigResponse:
    """Obtiene la configuración de un dispositivo."""
    try:
        config = await config_service.get_config(device_id)
        if not config:
            raise HTTPException(
                status_code=404, 
                detail=f"Configuration not found for device {device_id}"
            )
        return ConfigResponse(**config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")


@router.post("/device/{device_id}", response_model=ConfigResponse)
async def update_device_config(
    device_id: str,
    request: ConfigRequest,
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> ConfigResponse:
    """Actualiza la configuración de un dispositivo."""
    try:
        # Validar que el device_id coincida
        if request.device_id != device_id:
            raise HTTPException(
                status_code=400,
                detail="Device ID in path and body must match"
            )
        
        # Actualizar configuración
        updated_config = await config_service.update_config(
            device_id,
            request.config_data,
            backup=request.backup
        )
        
        return ConfigResponse(**updated_config)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


@router.delete("/device/{device_id}", response_model=dict)
async def delete_device_config(
    device_id: str,
    config_service: ConfigServiceInterface = Depends(get_config_service)
):
    """Elimina la configuración de un dispositivo."""
    try:
        await config_service.delete_config(device_id)
        return {"message": f"Configuration deleted for device {device_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting config: {str(e)}")


@router.get("/backups/{device_id}", response_model=List[BackupInfo])
async def list_device_backups(
    device_id: str,
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> List[BackupInfo]:
    """Lista backups de configuración para un dispositivo."""
    try:
        backups = await config_service.list_backups(device_id)
        return [BackupInfo(**backup) for backup in backups]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing backups: {str(e)}")


@router.post("/restore/{device_id}/{backup_id}", response_model=ConfigResponse)
async def restore_config_backup(
    device_id: str,
    backup_id: str,
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> ConfigResponse:
    """Restaura una configuración desde backup."""
    try:
        restored_config = await config_service.restore_backup(device_id, backup_id)
        return ConfigResponse(**restored_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring backup: {str(e)}")


@router.post("/validate", response_model=dict)
async def validate_config(
    request: ConfigRequest,
    config_service: ConfigServiceInterface = Depends(get_config_service)
):
    """Valida una configuración sin aplicarla."""
    try:
        is_valid, errors = await config_service.validate_config(
            request.device_id,
            request.config_data
        )
        
        return {
            "valid": is_valid,
            "errors": errors if not is_valid else [],
            "device_id": request.device_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating config: {str(e)}")


@router.get("/templates", response_model=List[str])
async def list_config_templates(
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> List[str]:
    """Lista plantillas de configuración disponibles."""
    try:
        templates = await config_service.list_templates()
        return templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing templates: {str(e)}")


@router.get("/template/{template_name}", response_model=Dict[str, Any])
async def get_config_template(
    template_name: str,
    config_service: ConfigServiceInterface = Depends(get_config_service)
) -> Dict[str, Any]:
    """Obtiene una plantilla de configuración."""
    try:
        template = await config_service.get_template(template_name)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template {template_name} not found"
            )
        return template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting template: {str(e)}")