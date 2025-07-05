"""Validadores para configuración del BomberCat.

Este módulo contiene las clases de validación usando Pydantic para
validar la configuración del dispositivo BomberCat antes de enviarla
al ESP32-S2.
"""

import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, ValidationError


class BomberCatConfig(BaseModel):
    """Modelo de configuración para el dispositivo BomberCat.
    
    Valida todos los parámetros de configuración según las especificaciones
    del dispositivo ESP32-S2.
    """
    
    mode: Literal["client", "host"] = Field(
        ...,
        description="Modo de operación del dispositivo"
    )
    
    wifi_ssid: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="SSID de la red Wi-Fi (máximo 32 bytes)"
    )
    
    wifi_password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Contraseña Wi-Fi (8-64 caracteres)"
    )
    
    encryption_key: str = Field(
        ...,
        pattern=r"^[0-9a-fA-F]{32}$",
        description="Clave de encriptación (32 caracteres hexadecimales)"
    )
    
    @field_validator('wifi_ssid')
    @classmethod
    def validate_wifi_ssid(cls, v):
        """Validar SSID Wi-Fi.
        
        Args:
            v: Valor del SSID a validar
            
        Returns:
            str: SSID validado
            
        Raises:
            ValueError: Si el SSID no cumple los requisitos
        """
        if not v or not v.strip():
            raise ValueError("SSID no puede estar vacío")
        
        # Verificar que no contenga caracteres de control
        if any(ord(c) < 32 or ord(c) == 127 for c in v):
            raise ValueError("SSID no puede contener caracteres de control")
        
        # Verificar longitud en bytes (UTF-8)
        if len(v.encode('utf-8')) > 32:
            raise ValueError("SSID excede 32 bytes en codificación UTF-8")
        
        return v.strip()
    
    @field_validator('wifi_password')
    @classmethod
    def validate_wifi_password(cls, v):
        """Validar contraseña Wi-Fi.
        
        Args:
            v: Valor de la contraseña a validar
            
        Returns:
            str: Contraseña validada
            
        Raises:
            ValueError: Si la contraseña no cumple los requisitos
        """
        if len(v) < 8:
            raise ValueError("Contraseña debe tener al menos 8 caracteres")
        
        if len(v) > 64:
            raise ValueError("Contraseña no puede exceder 64 caracteres")
        
        # Verificar que no contenga caracteres de control
        if any(ord(c) < 32 or ord(c) == 127 for c in v):
            raise ValueError("Contraseña no puede contener caracteres de control")
        
        return v
    
    @field_validator('encryption_key')
    @classmethod
    def validate_encryption_key(cls, v):
        """Validar clave de encriptación.
        
        Args:
            v: Valor de la clave a validar
            
        Returns:
            str: Clave validada en mayúsculas
            
        Raises:
            ValueError: Si la clave no cumple los requisitos
        """
        if not v:
            raise ValueError("Clave de encriptación no puede estar vacía")
        
        # Verificar formato hexadecimal de 32 caracteres
        if not re.match(r"^[0-9a-fA-F]{32}$", v):
            raise ValueError(
                "Clave de encriptación debe ser exactamente 32 caracteres hexadecimales"
            )
        
        return v.upper()  # Normalizar a mayúsculas
    
    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v):
        """Validar modo de operación.
        
        Args:
            v: Valor del modo a validar
            
        Returns:
            str: Modo validado en minúsculas
            
        Raises:
            ValueError: Si el modo no es válido
        """
        if v.lower() not in ["client", "host"]:
            raise ValueError("Modo debe ser 'client' o 'host'")
        
        return v.lower()
    
    def to_device_dict(self) -> dict:
        """Convertir configuración a formato para envío al dispositivo.
        
        Returns:
            dict: Configuración en formato JSON para el dispositivo
        """
        return {
            "mode": self.mode,
            "wifi_ssid": self.wifi_ssid,
            "wifi_password": self.wifi_password,
            "encryption_key": self.encryption_key
        }
    
    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "json_schema_extra": {
            "example": {
                "mode": "client",
                "wifi_ssid": "BomberCat_Network",
                "wifi_password": "SecurePassword123",
                "encryption_key": "0123456789ABCDEF0123456789ABCDEF"
            }
        }
    }


class ConfigValidator:
    """Validador de configuración para BomberCat.
    
    Proporciona métodos estáticos para validar configuraciones
    y manejar errores de validación.
    """
    
    @staticmethod
    def validate_config(config_data: dict) -> BomberCatConfig:
        """Validar datos de configuración.
        
        Args:
            config_data: Diccionario con datos de configuración
            
        Returns:
            BomberCatConfig: Configuración validada
            
        Raises:
            ValidationError: Si la configuración no es válida
        """
        try:
            return BomberCatConfig(**config_data)
        except ValidationError as e:
            # Re-lanzar la excepción original
            raise e
    
    @staticmethod
    def validate_partial_config(config_data: dict, 
                              current_config: BomberCatConfig) -> BomberCatConfig:
        """Validar configuración parcial usando valores actuales como base.
        
        Args:
            config_data: Datos parciales de configuración
            current_config: Configuración actual como base
            
        Returns:
            BomberCatConfig: Configuración completa validada
            
        Raises:
            ValidationError: Si la configuración no es válida
        """
        # Combinar configuración actual con nuevos valores
        merged_config = current_config.model_dump()
        merged_config.update(config_data)
        
        return ConfigValidator.validate_config(merged_config)
    
    @staticmethod
    def get_validation_errors(config_data: dict) -> list[str]:
        """Obtener lista de errores de validación sin lanzar excepción.
        
        Args:
            config_data: Diccionario con datos de configuración
            
        Returns:
            list[str]: Lista de mensajes de error, vacía si es válida
        """
        try:
            ConfigValidator.validate_config(config_data)
            return []
        except ValidationError as e:
            return [str(error) for error in e.errors()]
    
    @staticmethod
    def is_valid_config(config_data: dict) -> bool:
        """Verificar si una configuración es válida.
        
        Args:
            config_data: Diccionario con datos de configuración
            
        Returns:
            bool: True si la configuración es válida
        """
        try:
            ConfigValidator.validate_config(config_data)
            return True
        except ValidationError:
            return False
    
    @staticmethod
    def sanitize_config(config_data: dict) -> dict:
        """Sanitizar configuración removiendo campos no válidos.
        
        Args:
            config_data: Diccionario con datos de configuración
            
        Returns:
            dict: Configuración sanitizada con solo campos válidos
        """
        valid_fields = {"mode", "wifi_ssid", "wifi_password", "encryption_key"}
        return {k: v for k, v in config_data.items() if k in valid_fields}


# Funciones de conveniencia para validación rápida
def validate_mode(mode: str) -> bool:
    """Validar modo de operación.
    
    Args:
        mode: Modo a validar
        
    Returns:
        bool: True si el modo es válido
    """
    return mode.lower() in ["client", "host"]


def validate_wifi_ssid(ssid: str) -> bool:
    """Validar SSID Wi-Fi.
    
    Args:
        ssid: SSID a validar
        
    Returns:
        bool: True si el SSID es válido
    """
    try:
        if not ssid or len(ssid.encode('utf-8')) > 32:
            return False
        if any(ord(c) < 32 or ord(c) == 127 for c in ssid):
            return False
        return True
    except Exception:
        return False


def validate_wifi_password(password: str) -> bool:
    """Validar contraseña Wi-Fi.
    
    Args:
        password: Contraseña a validar
        
    Returns:
        bool: True si la contraseña es válida
    """
    try:
        if len(password) < 8 or len(password) > 64:
            return False
        if any(ord(c) < 32 or ord(c) == 127 for c in password):
            return False
        return True
    except Exception:
        return False


def validate_encryption_key(key: str) -> bool:
    """Validar clave de encriptación.
    
    Args:
        key: Clave a validar
        
    Returns:
        bool: True si la clave es válida
    """
    try:
        return bool(re.match(r"^[0-9a-fA-F]{32}$", key))
    except Exception:
        return False