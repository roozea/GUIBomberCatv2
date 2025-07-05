"""Device management API routes.

Endpoints para gestión y monitoreo de dispositivos conectados.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from api.dependencies import get_device_service
from adapters.interfaces import BaseService


router = APIRouter()


class DeviceInfo(BaseModel):
    """Information model para dispositivos."""
    device_id: str
    name: str
    type: str  # "esp32", "arduino", "relay_board", etc.
    status: str  # "online", "offline", "error", "unknown"
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    firmware_version: Optional[str] = None
    last_seen: Optional[str] = None
    uptime: Optional[int] = None  # segundos
    rssi: Optional[int] = None  # señal WiFi


class DeviceMetrics(BaseModel):
    """Metrics model para dispositivos."""
    device_id: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    temperature: Optional[float] = None
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    timestamp: str


class DeviceCommand(BaseModel):
    """Command model para dispositivos."""
    device_id: str
    command: str
    parameters: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = 30


class DeviceLog(BaseModel):
    """Log entry model para dispositivos."""
    device_id: str
    timestamp: str
    level: str  # "debug", "info", "warning", "error"
    message: str
    source: Optional[str] = None


@router.get("/list", response_model=List[DeviceInfo])
async def list_devices(
    status_filter: Optional[str] = None,
    device_type: Optional[str] = None,
    device_service: BaseService = Depends(get_device_service)
) -> List[DeviceInfo]:
    """Lista todos los dispositivos conectados."""
    try:
        devices = await device_service.list_devices(
            status_filter=status_filter,
            device_type=device_type
        )
        return [DeviceInfo(**device) for device in devices]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing devices: {str(e)}")


@router.get("/info/{device_id}", response_model=DeviceInfo)
async def get_device_info(
    device_id: str,
    device_service: BaseService = Depends(get_device_service)
) -> DeviceInfo:
    """Obtiene información detallada de un dispositivo."""
    try:
        device = await device_service.get_device_info(device_id)
        if not device:
            raise HTTPException(
                status_code=404,
                detail=f"Device {device_id} not found"
            )
        return DeviceInfo(**device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting device info: {str(e)}")


@router.get("/metrics/{device_id}", response_model=List[DeviceMetrics])
async def get_device_metrics(
    device_id: str,
    hours: Optional[int] = 24,
    device_service: BaseService = Depends(get_device_service)
) -> List[DeviceMetrics]:
    """Obtiene métricas históricas de un dispositivo."""
    try:
        metrics = await device_service.get_device_metrics(device_id, hours)
        return [DeviceMetrics(**metric) for metric in metrics]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting device metrics: {str(e)}")


@router.get("/metrics/{device_id}/latest", response_model=DeviceMetrics)
async def get_latest_metrics(
    device_id: str,
    device_service: BaseService = Depends(get_device_service)
) -> DeviceMetrics:
    """Obtiene las métricas más recientes de un dispositivo."""
    try:
        metrics = await device_service.get_latest_metrics(device_id)
        if not metrics:
            raise HTTPException(
                status_code=404,
                detail=f"No metrics found for device {device_id}"
            )
        return DeviceMetrics(**metrics)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting latest metrics: {str(e)}")


@router.post("/command", response_model=dict)
async def send_device_command(
    command: DeviceCommand,
    device_service: BaseService = Depends(get_device_service)
):
    """Envía un comando a un dispositivo."""
    try:
        result = await device_service.send_command(
            command.device_id,
            command.command,
            command.parameters,
            command.timeout
        )
        
        return {
            "message": "Command sent successfully",
            "device_id": command.device_id,
            "command": command.command,
            "result": result.get("result"),
            "execution_time": result.get("execution_time")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending command: {str(e)}")


@router.post("/restart/{device_id}", response_model=dict)
async def restart_device(
    device_id: str,
    device_service: BaseService = Depends(get_device_service)
):
    """Reinicia un dispositivo."""
    try:
        result = await device_service.restart_device(device_id)
        return {
            "message": f"Restart command sent to device {device_id}",
            "device_id": device_id,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restarting device: {str(e)}")


@router.get("/logs/{device_id}", response_model=List[DeviceLog])
async def get_device_logs(
    device_id: str,
    limit: Optional[int] = 100,
    level: Optional[str] = None,
    device_service: BaseService = Depends(get_device_service)
) -> List[DeviceLog]:
    """Obtiene logs de un dispositivo."""
    try:
        logs = await device_service.get_device_logs(
            device_id,
            limit=limit,
            level=level
        )
        return [DeviceLog(**log) for log in logs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting device logs: {str(e)}")


@router.post("/discover", response_model=List[DeviceInfo])
async def discover_devices(
    network_range: Optional[str] = None,
    timeout: Optional[int] = 30,
    device_service: BaseService = Depends(get_device_service)
) -> List[DeviceInfo]:
    """Descubre dispositivos en la red."""
    try:
        devices = await device_service.discover_devices(
            network_range=network_range,
            timeout=timeout
        )
        return [DeviceInfo(**device) for device in devices]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error discovering devices: {str(e)}")


@router.post("/register", response_model=dict)
async def register_device(
    device_info: DeviceInfo,
    device_service: BaseService = Depends(get_device_service)
):
    """Registra un nuevo dispositivo manualmente."""
    try:
        result = await device_service.register_device(device_info.dict())
        return {
            "message": "Device registered successfully",
            "device_id": device_info.device_id,
            "registration_id": result.get("registration_id")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registering device: {str(e)}")


@router.delete("/remove/{device_id}", response_model=dict)
async def remove_device(
    device_id: str,
    device_service: BaseService = Depends(get_device_service)
):
    """Elimina un dispositivo del sistema."""
    try:
        await device_service.remove_device(device_id)
        return {
            "message": f"Device {device_id} removed successfully",
            "device_id": device_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing device: {str(e)}")


@router.get("/health", response_model=Dict[str, Any])
async def get_devices_health(
    device_service: BaseService = Depends(get_device_service)
) -> Dict[str, Any]:
    """Obtiene el estado de salud general de todos los dispositivos."""
    try:
        health = await device_service.get_health_summary()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting devices health: {str(e)}")


@router.post("/ping/{device_id}", response_model=dict)
async def ping_device(
    device_id: str,
    device_service: BaseService = Depends(get_device_service)
):
    """Hace ping a un dispositivo para verificar conectividad."""
    try:
        result = await device_service.ping_device(device_id)
        return {
            "device_id": device_id,
            "reachable": result.get("reachable", False),
            "latency_ms": result.get("latency_ms"),
            "timestamp": result.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pinging device: {str(e)}")


@router.get("/types", response_model=List[str])
async def get_device_types(
    device_service: BaseService = Depends(get_device_service)
) -> List[str]:
    """Lista los tipos de dispositivos soportados."""
    try:
        types = await device_service.get_supported_device_types()
        return types
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting device types: {str(e)}")