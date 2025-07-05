"""Módulo de configuración para BomberCat.

Este módulo proporciona funcionalidades para configurar dinámicamente
el dispositivo BomberCat incluyendo modo (Client/Host), configuración Wi-Fi,
y claves de encriptación. La configuración se guarda en NVS del ESP32-S2.
"""

from modules.bombercat_config.validators import ConfigValidator, BomberCatConfig
from modules.bombercat_config.backup import backup_config, rollback
from modules.bombercat_config.transaction import ConfigTransaction

__all__ = [
    "ConfigValidator",
    "BomberCatConfig", 
    "backup_config",
    "rollback",
    "ConfigTransaction"
]

__version__ = "1.0.0"