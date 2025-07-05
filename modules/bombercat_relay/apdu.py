"""Parser y Validador APDU para NFC Relay

Implementa parsing y validación de comandos APDU según ISO 7816-4.
Soporta detección de comandos completos y validación CRC.
"""

import struct
from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class APDU:
    """Comando APDU parseado.
    
    Estructura según ISO 7816-4:
    - CLA: Clase de instrucción (1 byte)
    - INS: Código de instrucción (1 byte) 
    - P1, P2: Parámetros (1 byte cada uno)
    - Lc: Longitud de datos de comando (0-3 bytes)
    - Data: Datos de comando (0-65535 bytes)
    - Le: Longitud esperada de respuesta (0-3 bytes)
    """
    cla: int
    ins: int
    p1: int
    p2: int
    lc: Optional[int] = None
    data: Optional[bytes] = None
    le: Optional[int] = None
    raw: Optional[bytes] = None
    
    @property
    def is_valid(self) -> bool:
        """Verifica si el APDU es válido."""
        # Verificar rangos básicos
        if not (0 <= self.cla <= 0xFF):
            return False
        if not (0 <= self.ins <= 0xFF):
            return False
        if not (0 <= self.p1 <= 0xFF):
            return False
        if not (0 <= self.p2 <= 0xFF):
            return False
            
        # Verificar consistencia de datos
        if self.lc is not None:
            if self.lc < 0 or self.lc > 65535:
                return False
            if self.data is None and self.lc > 0:
                return False
            if self.data is not None and len(self.data) != self.lc:
                return False
                
        if self.le is not None and (self.le < 0 or self.le > 65536):
            return False
            
        return True
    
    @property
    def expected_length(self) -> int:
        """Longitud total esperada del APDU en bytes."""
        length = 4  # CLA + INS + P1 + P2
        
        if self.lc is not None:
            if self.lc <= 255:
                length += 1  # Lc corto
            else:
                length += 3  # Lc extendido
            length += self.lc  # Datos
            
        if self.le is not None:
            if self.le <= 256:
                length += 1  # Le corto
            else:
                length += 3  # Le extendido
                
        return length
    
    def to_bytes(self) -> bytes:
        """Convierte el APDU a bytes."""
        if self.raw:
            return self.raw
            
        result = bytearray([self.cla, self.ins, self.p1, self.p2])
        
        # Agregar Lc y datos si existen
        if self.lc is not None and self.lc > 0:
            if self.lc <= 255:
                result.append(self.lc)
            else:
                result.extend([0, (self.lc >> 8) & 0xFF, self.lc & 0xFF])
            
            if self.data:
                result.extend(self.data)
        
        # Agregar Le si existe
        if self.le is not None:
            if self.le <= 256:
                result.append(0 if self.le == 256 else self.le)
            else:
                result.extend([0, (self.le >> 8) & 0xFF, self.le & 0xFF])
        
        return bytes(result)
    
    def calculate_crc(self) -> int:
        """Calcula CRC simple XOR según ISO14443-3."""
        data = self.to_bytes()
        crc = 0
        for byte in data:
            crc ^= byte
        return crc


def is_complete(buffer: Union[bytes, bytearray, memoryview]) -> bool:
    """Verifica si el buffer contiene un APDU completo.
    
    Args:
        buffer: Buffer con datos APDU
        
    Returns:
        True si contiene un APDU completo
    """
    if len(buffer) < 4:
        return False
    
    try:
        offset = 4
        
        # Si solo hay cabecera, está completo
        if len(buffer) == 4:
            return True
        
        # Verificar si hay Lc/Le
        if offset < len(buffer):
            remaining_bytes = len(buffer) - offset
            
            # Case 2: Solo Le (5 bytes total)
            if remaining_bytes == 1:
                return True
            
            # Case 3 o 4: Hay Lc
            elif remaining_bytes > 1:
                # Leer Lc
                if buffer[offset] == 0 and remaining_bytes >= 3:
                    # Lc extendido
                    if remaining_bytes < 3:
                        return False
                    lc = (buffer[offset + 1] << 8) | buffer[offset + 2]
                    offset += 3
                else:
                    # Lc corto
                    lc = buffer[offset]
                    offset += 1
                
                # Verificar que hay suficientes datos
                if lc > 0:
                    if offset + lc > len(buffer):
                        return False
                    offset += lc
                
                # Si hay bytes restantes, debe ser Le
                if offset < len(buffer):
                    remaining = len(buffer) - offset
                    if remaining == 1:
                        return True  # Le corto
                    elif remaining == 3 and buffer[offset] == 0:
                        return True  # Le extendido
                    else:
                        return False  # Bytes extra inválidos
                
                return True
        
        return True
        
    except Exception:
        return False


def parse_apdu(buffer: Union[bytes, bytearray, memoryview], validate: bool = True) -> Optional[APDU]:
    """Parsea un APDU desde un buffer.
    
    Args:
        buffer: Buffer con datos APDU
        validate: Si validar el APDU parseado
        
    Returns:
        APDU parseado o None si hay error
    """
    if len(buffer) < 4:
        return None
    
    try:
        # Leer cabecera obligatoria
        cla = buffer[0]
        ins = buffer[1]
        p1 = buffer[2]
        p2 = buffer[3]
        
        offset = 4
        lc = None
        data = None
        le = None
        
        # Determinar si hay más datos
        if offset < len(buffer):
            remaining_bytes = len(buffer) - offset
            
            # Case 2: Solo Le (5 bytes total: CLA+INS+P1+P2+Le)
            if remaining_bytes == 1:
                le = buffer[offset] if buffer[offset] != 0 else 256
            
            # Case 3 o 4: Hay Lc (y posiblemente Le)
            elif remaining_bytes > 1:
                # Verificar si es Lc extendido
                if buffer[offset] == 0 and remaining_bytes >= 3:
                    # Lc extendido (3 bytes: 00 + 2 bytes longitud)
                    lc = (buffer[offset + 1] << 8) | buffer[offset + 2]
                    offset += 3
                else:
                    # Lc corto (1 byte)
                    lc = buffer[offset]
                    offset += 1
                
                # Leer datos si Lc >= 0 (incluye Lc=0)
                if lc is not None:
                    if lc > 0:
                        if offset + lc > len(buffer):
                            # No hay suficientes datos
                            return None
                        data = bytes(buffer[offset:offset + lc])
                        offset += lc
                    else:
                        # Lc=0, datos vacíos
                        data = b""
                
                # Verificar si hay Le después de los datos
                if offset < len(buffer):
                    remaining = len(buffer) - offset
                    
                    if remaining == 1:
                        # Le corto
                        le = buffer[offset] if buffer[offset] != 0 else 256
                    elif remaining == 3 and buffer[offset] == 0:
                        # Le extendido
                        le = (buffer[offset + 1] << 8) | buffer[offset + 2]
                        if le == 0:
                            le = 65536
        
        # Crear APDU
        apdu = APDU(
            cla=cla,
            ins=ins,
            p1=p1,
            p2=p2,
            lc=lc,
            data=data,
            le=le,
            raw=bytes(buffer)
        )
        
        # Validar si se solicita
        if validate and not apdu.is_valid:
            return None
            
        return apdu
        
    except (IndexError, struct.error, ValueError):
        return None


def validate_apdu_structure(buffer: Union[bytes, bytearray, memoryview]) -> tuple[bool, str]:
    """Valida la estructura de un APDU.
    
    Args:
        buffer: Buffer con datos APDU
        
    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if len(buffer) < 4:
        return False, "APDU debe tener al menos 4 bytes (CLA+INS+P1+P2)"
    
    apdu = parse_apdu(buffer, validate=False)
    if apdu is None:
        return False, "No se pudo parsear el APDU"
    
    if not apdu.is_valid:
        return False, "APDU tiene estructura inválida"
    
    # Verificaciones adicionales
    if apdu.ins in [0x00, 0xFF]:
        return False, f"INS inválido: 0x{apdu.ins:02X}"
    
    if apdu.cla & 0x0F == 0x0F:
        return False, f"CLA reservado: 0x{apdu.cla:02X}"
    
    return True, "APDU válido"


def create_response_apdu(data: Optional[bytes] = None, sw1: int = 0x90, sw2: int = 0x00) -> bytes:
    """Crea un APDU de respuesta.
    
    Args:
        data: Datos de respuesta opcionales
        sw1: Status Word 1 (por defecto 0x90 = éxito)
        sw2: Status Word 2 (por defecto 0x00)
        
    Returns:
        APDU de respuesta en bytes
    """
    result = bytearray()
    
    if data:
        result.extend(data)
    
    result.extend([sw1, sw2])
    
    return bytes(result)


# Constantes APDU comunes
class APDUConstants:
    """Constantes APDU comunes."""
    
    # Status Words comunes
    SW_SUCCESS = (0x90, 0x00)
    SW_WRONG_LENGTH = (0x67, 0x00)
    SW_SECURITY_STATUS = (0x69, 0x82)
    SW_WRONG_DATA = (0x6A, 0x80)
    SW_WRONG_P1P2 = (0x6A, 0x86)
    SW_INS_NOT_SUPPORTED = (0x6D, 0x00)
    SW_CLA_NOT_SUPPORTED = (0x6E, 0x00)
    
    # Clases comunes
    CLA_ISO = 0x00
    CLA_PROPRIETARY = 0x80
    
    # Instrucciones comunes
    INS_SELECT = 0xA4
    INS_READ_BINARY = 0xB0
    INS_UPDATE_BINARY = 0xD6
    INS_GET_RESPONSE = 0xC0