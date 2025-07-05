"""API Routes package.

Centraliza todos los routers de la API bajo el prefijo /api/v1/.
"""

from fastapi import APIRouter, FastAPI
from . import flash_routes, config_routes, relay_routes, mqtt_routes, device_routes


def register_routes(app: FastAPI) -> None:
    """Registra todas las rutas de la API con el prefijo /api/v1/.
    
    Args:
        app: Instancia de FastAPI donde registrar las rutas
    """
    # Router principal para v1
    v1_router = APIRouter(prefix="/api/v1", tags=["API v1"])
    
    # Incluir todos los sub-routers
    v1_router.include_router(
        flash_routes.router,
        prefix="/flash",
        tags=["Flash"]
    )
    
    v1_router.include_router(
        config_routes.router,
        prefix="/config",
        tags=["Configuration"]
    )
    
    v1_router.include_router(
        relay_routes.router,
        prefix="/relay",
        tags=["Relay"]
    )
    
    v1_router.include_router(
        mqtt_routes.router,
        prefix="/mqtt",
        tags=["MQTT"]
    )
    
    v1_router.include_router(
        device_routes.router,
        prefix="/devices",
        tags=["Devices"]
    )
    
    # Registrar el router v1 en la app
    app.include_router(v1_router)
    
    # Rutas especiales que no van bajo /api/v1/
    @app.get("/", tags=["Root"])
    async def root():
        """Endpoint raíz."""
        return {"message": "BomberCat Integrator API", "version": "2.0", "docs": "/docs"}
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "bombercat-integrator"}