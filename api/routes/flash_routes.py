"""Flash service API routes.

Endpoints para operaciones de flasheo de firmware.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel

from api.dependencies import get_flash_service
from adapters.interfaces import FlashServiceInterface


router = APIRouter()


class FlashRequest(BaseModel):
    """Request model para operaciones de flash."""
    port: str
    firmware_path: str
    baud_rate: Optional[int] = 115200
    chip_type: Optional[str] = "esp32"
    erase_flash: Optional[bool] = False


class FlashStatus(BaseModel):
    """Status model para operaciones de flash."""
    port: str
    status: str  # "idle", "flashing", "success", "error"
    progress: Optional[int] = None
    message: Optional[str] = None


@router.get("/ports", response_model=List[str])
async def list_serial_ports(
    flash_service: FlashServiceInterface = Depends(get_flash_service)
) -> List[str]:
    """Lista puertos seriales disponibles."""
    try:
        ports = await flash_service.list_ports()
        return ports
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing ports: {str(e)}")


@router.post("/flash", response_model=dict)
async def flash_firmware(
    request: FlashRequest,
    background_tasks: BackgroundTasks,
    flash_service: FlashServiceInterface = Depends(get_flash_service)
):
    """Inicia proceso de flasheo de firmware."""
    try:
        # Validar puerto
        available_ports = await flash_service.list_ports()
        if request.port not in available_ports:
            raise HTTPException(
                status_code=400, 
                detail=f"Port {request.port} not available"
            )
        
        # Iniciar flasheo en background
        background_tasks.add_task(
            flash_service.flash_firmware,
            request.port,
            request.firmware_path,
            request.baud_rate,
            request.chip_type,
            request.erase_flash
        )
        
        return {
            "message": "Flash process started",
            "port": request.port,
            "firmware": request.firmware_path
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting flash: {str(e)}")


@router.get("/status/{port}", response_model=FlashStatus)
async def get_flash_status(
    port: str,
    flash_service: FlashServiceInterface = Depends(get_flash_service)
) -> FlashStatus:
    """Obtiene el estado del proceso de flasheo para un puerto."""
    try:
        status = await flash_service.get_flash_status(port)
        return FlashStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.post("/stop/{port}", response_model=dict)
async def stop_flash(
    port: str,
    flash_service: FlashServiceInterface = Depends(get_flash_service)
):
    """Detiene el proceso de flasheo para un puerto."""
    try:
        await flash_service.stop_flash(port)
        return {"message": f"Flash process stopped for port {port}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping flash: {str(e)}")


@router.get("/firmware", response_model=List[str])
async def list_firmware_files(
    flash_service: FlashServiceInterface = Depends(get_flash_service)
) -> List[str]:
    """Lista archivos de firmware disponibles."""
    try:
        firmware_files = await flash_service.list_firmware_files()
        return firmware_files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing firmware: {str(e)}")