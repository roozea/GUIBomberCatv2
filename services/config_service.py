"""Config service para gestión de configuraciones."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigService:
    """Servicio para gestión de configuraciones de dispositivos."""
    
    def __init__(self):
        """Inicializar el servicio de configuración."""
        self.current_config = {
            "device_name": "BomberCat-001",
            "wifi_ssid": "",
            "wifi_password": "",
            "mqtt_broker": "localhost",
            "mqtt_port": 1883,
            "relay_enabled": True,
            "relay_port": 8080
        }
        logger.info("ConfigService inicializado")
    
    async def update_config(self, config_data: Dict[str, Any]) -> dict:
        """Actualiza la configuración del dispositivo.
        
        Args:
            config_data: Datos de configuración a actualizar
            
        Returns:
            Resultado de la actualización
        """
        try:
            logger.info(f"Actualizando configuración: {config_data}")
            
            # Validar y actualizar configuración
            for key, value in config_data.items():
                if key in self.current_config:
                    self.current_config[key] = value
                    logger.info(f"Configuración actualizada: {key} = {value}")
                else:
                    logger.warning(f"Clave de configuración desconocida: {key}")
            
            return {
                "success": True,
                "message": "Configuración actualizada exitosamente",
                "updated_config": self.current_config
            }
            
        except Exception as e:
            logger.error(f"Error actualizando configuración: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuración actual."""
        return self.current_config.copy()
    
    async def validate_config(self, config_data: Dict[str, Any]) -> dict:
        """Valida una configuración.
        
        Args:
            config_data: Datos de configuración a validar
            
        Returns:
            Resultado de la validación
        """
        try:
            errors = []
            
            # Validaciones básicas
            if "wifi_ssid" in config_data and len(config_data["wifi_ssid"]) > 32:
                errors.append("SSID demasiado largo (máximo 32 caracteres)")
            
            if "mqtt_port" in config_data:
                port = config_data["mqtt_port"]
                if not isinstance(port, int) or port < 1 or port > 65535:
                    errors.append("Puerto MQTT inválido (1-65535)")
            
            if "relay_port" in config_data:
                port = config_data["relay_port"]
                if not isinstance(port, int) or port < 1024 or port > 65535:
                    errors.append("Puerto relay inválido (1024-65535)")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error validando configuración: {e}")
            return {
                "valid": False,
                "errors": [str(e)]
            }