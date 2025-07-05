"""Relay service API routes.

Endpoints para control de relés y dispositivos de conmutación.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from api.dependencies import get_relay_service
from adapters.interfaces import RelayServiceInterface


router = APIRouter()


class RelayCommand(BaseModel):
    """Command model para control de relés."""
    relay_id: str
    action: str  # "on", "off", "toggle"
    duration: Optional[int] = None  # Duración en segundos para acciones temporales


class RelayStatus(BaseModel):
    """Status model para relés."""
    relay_id: str
    state: str  # "on", "off", "unknown"
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    last_update: str


class RelayInfo(BaseModel):
    """Information model para relés."""
    relay_id: str
    name: str
    description: Optional[str] = None
    type: str  # "digital", "analog", "pwm"
    pin: Optional[int] = None
    max_voltage: Optional[float] = None
    max_current: Optional[float] = None


@router.get("/list", response_model=List[RelayInfo])
async def list_relays(
    relay_service: RelayServiceInterface = Depends(get_relay_service)
) -> List[RelayInfo]:
    """Lista todos los relés disponibles."""
    try:
        relays = await relay_service.list_relays()
        return [RelayInfo(**relay) for relay in relays]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing relays: {str(e)}")


@router.get("/status", response_model=List[RelayStatus])
async def get_all_relay_status(
    relay_service: RelayServiceInterface = Depends(get_relay_service)
) -> List[RelayStatus]:
    """Obtiene el estado de todos los relés."""
    try:
        statuses = await relay_service.get_all_status()
        return [RelayStatus(**status) for status in statuses]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting relay status: {str(e)}")


@router.get("/status/{relay_id}", response_model=RelayStatus)
async def get_relay_status(
    relay_id: str,
    relay_service: RelayServiceInterface = Depends(get_relay_service)
) -> RelayStatus:
    """Obtiene el estado de un relé específico."""
    try:
        status = await relay_service.get_status(relay_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Relay {relay_id} not found"
            )
        return RelayStatus(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting relay status: {str(e)}")


@router.post("/control", response_model=dict)
async def control_relay(
    command: RelayCommand,
    relay_service: RelayServiceInterface = Depends(get_relay_service)
):
    """Controla un relé específico."""
    try:
        # Validar acción
        valid_actions = ["on", "off", "toggle"]
        if command.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Must be one of: {valid_actions}"
            )
        
        # Ejecutar comando
        result = await relay_service.control_relay(
            command.relay_id,
            command.action,
            command.duration
        )
        
        return {
            "message": f"Relay {command.relay_id} {command.action} command executed",
            "relay_id": command.relay_id,
            "action": command.action,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error controlling relay: {str(e)}")


@router.post("/control/{relay_id}/{action}", response_model=dict)
async def control_relay_simple(
    relay_id: str,
    action: str,
    duration: Optional[int] = None,
    relay_service: RelayServiceInterface = Depends(get_relay_service)
):
    """Controla un relé con parámetros en la URL (método simplificado)."""
    command = RelayCommand(
        relay_id=relay_id,
        action=action,
        duration=duration
    )
    return await control_relay(command, relay_service)


@router.post("/batch", response_model=List[dict])
async def control_multiple_relays(
    commands: List[RelayCommand],
    relay_service: RelayServiceInterface = Depends(get_relay_service)
) -> List[dict]:
    """Controla múltiples relés en una sola operación."""
    results = []
    
    for command in commands:
        try:
            result = await relay_service.control_relay(
                command.relay_id,
                command.action,
                command.duration
            )
            results.append({
                "relay_id": command.relay_id,
                "action": command.action,
                "status": "success",
                "result": result
            })
        except Exception as e:
            results.append({
                "relay_id": command.relay_id,
                "action": command.action,
                "status": "error",
                "error": str(e)
            })
    
    return results


@router.get("/metrics/{relay_id}", response_model=Dict[str, Any])
async def get_relay_metrics(
    relay_id: str,
    hours: Optional[int] = 24,
    relay_service: RelayServiceInterface = Depends(get_relay_service)
) -> Dict[str, Any]:
    """Obtiene métricas históricas de un relé."""
    try:
        metrics = await relay_service.get_metrics(relay_id, hours)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")


@router.post("/emergency_stop", response_model=dict)
async def emergency_stop_all(
    relay_service: RelayServiceInterface = Depends(get_relay_service)
):
    """Detiene todos los relés inmediatamente (parada de emergencia)."""
    try:
        result = await relay_service.emergency_stop()
        return {
            "message": "Emergency stop executed",
            "stopped_relays": result.get("stopped_relays", []),
            "timestamp": result.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in emergency stop: {str(e)}")


@router.get("/schedules/{relay_id}", response_model=List[Dict[str, Any]])
async def get_relay_schedules(
    relay_id: str,
    relay_service: RelayServiceInterface = Depends(get_relay_service)
) -> List[Dict[str, Any]]:
    """Obtiene programaciones activas para un relé."""
    try:
        schedules = await relay_service.get_schedules(relay_id)
        return schedules
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting schedules: {str(e)}")


@router.post("/schedule/{relay_id}", response_model=dict)
async def create_relay_schedule(
    relay_id: str,
    schedule_data: Dict[str, Any],
    relay_service: RelayServiceInterface = Depends(get_relay_service)
):
    """Crea una nueva programación para un relé."""
    try:
        schedule_id = await relay_service.create_schedule(relay_id, schedule_data)
        return {
            "message": "Schedule created successfully",
            "relay_id": relay_id,
            "schedule_id": schedule_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating schedule: {str(e)}")