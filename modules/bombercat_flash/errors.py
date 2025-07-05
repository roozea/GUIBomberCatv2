"""Excepciones específicas para el Flash Wizard.

Este módulo define todas las excepciones personalizadas para el proceso
de flasheo, proporcionando mensajes de error amigables y específicos.
"""

from typing import Optional


class FlashError(Exception):
    """Excepción base para errores de flasheo.
    
    Todas las excepciones específicas del Flash Wizard heredan de esta clase.
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Inicializa la excepción base.
        
        Args:
            message: Mensaje de error amigable
            original_error: Excepción original que causó este error
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error
        
    def __str__(self) -> str:
        """Retorna representación string del error."""
        if self.original_error:
            return f"{self.message} (Causa: {self.original_error})"
        return self.message


class PortBusyError(FlashError):
    """Error cuando el puerto serie está ocupado o no disponible.
    
    Se lanza cuando:
    - El puerto está siendo usado por otra aplicación
    - No hay permisos para acceder al puerto
    - El dispositivo no está conectado
    """
    
    def __init__(self, port: str, original_error: Optional[Exception] = None):
        """Inicializa error de puerto ocupado.
        
        Args:
            port: Puerto serie que está ocupado
            original_error: Excepción original
        """
        message = (
            f"Puerto {port} no disponible. "
            "Verifica que el dispositivo esté conectado y que no esté "
            "siendo usado por otra aplicación (monitor serie, IDE, etc.)"
        )
        super().__init__(message, original_error)
        self.port = port


class SyncError(FlashError):
    """Error de sincronización con el dispositivo ESP32.
    
    Se lanza cuando:
    - El dispositivo no responde a comandos de sincronización
    - El bootloader no está en modo de descarga
    - Problemas de comunicación serie
    """
    
    def __init__(self, device_type: str = "ESP32", original_error: Optional[Exception] = None):
        """Inicializa error de sincronización.
        
        Args:
            device_type: Tipo de dispositivo (ESP32, ESP32-S2, etc.)
            original_error: Excepción original
        """
        message = (
            f"No se pudo sincronizar con el dispositivo {device_type}. "
            "Asegúrate de que esté en modo bootloader (mantén presionado BOOT "
            "mientras presionas RESET, luego suelta RESET y después BOOT)."
        )
        super().__init__(message, original_error)
        self.device_type = device_type


class FlashTimeout(FlashError):
    """Error de timeout durante el proceso de flasheo.
    
    Se lanza cuando:
    - El flasheo toma más tiempo del esperado
    - El dispositivo deja de responder durante el flasheo
    - Problemas de velocidad de baudios
    """
    
    def __init__(self, timeout_seconds: int, operation: str = "flasheo", original_error: Optional[Exception] = None):
        """Inicializa error de timeout.
        
        Args:
            timeout_seconds: Tiempo de timeout en segundos
            operation: Operación que falló (flasheo, verificación, etc.)
            original_error: Excepción original
        """
        message = (
            f"Timeout durante {operation} ({timeout_seconds}s). "
            "El dispositivo puede estar desconectado o la velocidad "
            "de baudios puede ser muy alta para tu cable USB."
        )
        super().__init__(message, original_error)
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class ChecksumMismatch(FlashError):
    """Error de verificación de checksum.
    
    Se lanza cuando:
    - El firmware flasheado no coincide con el archivo original
    - Hay corrupción de datos durante el flasheo
    - El archivo de firmware está corrupto
    """
    
    def __init__(self, expected: str, actual: str, original_error: Optional[Exception] = None):
        """Inicializa error de checksum.
        
        Args:
            expected: Checksum esperado
            actual: Checksum actual
            original_error: Excepción original
        """
        message = (
            f"Verificación de firmware falló. "
            f"Checksum esperado: {expected}, obtenido: {actual}. "
            "El firmware puede estar corrupto o el flasheo falló."
        )
        super().__init__(message, original_error)
        self.expected = expected
        self.actual = actual


class InvalidFirmwareError(FlashError):
    """Error cuando el archivo de firmware es inválido.
    
    Se lanza cuando:
    - El archivo no tiene el formato correcto
    - Los magic bytes no coinciden
    - El archivo está corrupto o incompleto
    """
    
    def __init__(self, reason: str, file_path: Optional[str] = None, original_error: Optional[Exception] = None):
        """Inicializa error de firmware inválido.
        
        Args:
            reason: Razón específica por la que es inválido
            file_path: Ruta del archivo de firmware
            original_error: Excepción original
        """
        file_info = f" ({file_path})" if file_path else ""
        message = f"Archivo de firmware inválido{file_info}: {reason}"
        super().__init__(message, original_error)
        self.reason = reason
        self.file_path = file_path


class DeviceNotFoundError(FlashError):
    """Error cuando no se encuentra el dispositivo.
    
    Se lanza cuando:
    - No hay dispositivos ESP32 conectados
    - El dispositivo no es reconocido
    - Problemas de drivers USB
    """
    
    def __init__(self, searched_ports: Optional[list[str]] = None, original_error: Optional[Exception] = None):
        """Inicializa error de dispositivo no encontrado.
        
        Args:
            searched_ports: Lista de puertos donde se buscó
            original_error: Excepción original
        """
        if searched_ports:
            ports_info = f" Puertos verificados: {', '.join(searched_ports)}"
        else:
            ports_info = ""
            
        message = (
            f"No se encontró ningún dispositivo ESP32 conectado.{ports_info} "
            "Verifica la conexión USB y que los drivers estén instalados."
        )
        super().__init__(message, original_error)
        self.searched_ports = searched_ports or []


class InsufficientSpaceError(FlashError):
    """Error cuando no hay suficiente espacio en la flash.
    
    Se lanza cuando:
    - El firmware es más grande que la capacidad de la flash
    - La partición de destino es muy pequeña
    """
    
    def __init__(self, required_size: int, available_size: int, original_error: Optional[Exception] = None):
        """Inicializa error de espacio insuficiente.
        
        Args:
            required_size: Tamaño requerido en bytes
            available_size: Tamaño disponible en bytes
            original_error: Excepción original
        """
        required_mb = required_size / (1024 * 1024)
        available_mb = available_size / (1024 * 1024)
        
        message = (
            f"Espacio insuficiente en flash. "
            f"Requerido: {required_mb:.2f} MB, disponible: {available_mb:.2f} MB"
        )
        super().__init__(message, original_error)
        self.required_size = required_size
        self.available_size = available_size


class UnsupportedDeviceError(FlashError):
    """Error cuando el dispositivo no es compatible.
    
    Se lanza cuando:
    - El chip detectado no es ESP32-S2
    - La versión del bootloader no es compatible
    - El dispositivo está en un estado no soportado
    """
    
    def __init__(self, detected_chip: str, supported_chips: list[str], original_error: Optional[Exception] = None):
        """Inicializa error de dispositivo no soportado.
        
        Args:
            detected_chip: Chip detectado
            supported_chips: Lista de chips soportados
            original_error: Excepción original
        """
        supported_list = ", ".join(supported_chips)
        message = (
            f"Dispositivo {detected_chip} no soportado. "
            f"Chips soportados: {supported_list}"
        )
        super().__init__(message, original_error)
        self.detected_chip = detected_chip
        self.supported_chips = supported_chips


def map_esptool_error(error: Exception, context: str = "") -> FlashError:
    """Mapea errores de esptool a nuestras excepciones específicas.
    
    Args:
        error: Excepción original de esptool
        context: Contexto adicional sobre cuándo ocurrió el error
        
    Returns:
        FlashError: Excepción específica mapeada
    """
    error_str = str(error).lower()
    
    # Mapeo de errores comunes de esptool
    if "could not open" in error_str or "permission denied" in error_str:
        # Extraer puerto del mensaje si es posible
        port = "desconocido"
        if "port" in error_str:
            parts = error_str.split()
            for i, part in enumerate(parts):
                if "port" in part and i + 1 < len(parts):
                    port = parts[i + 1].strip("'\"")
                    break
        return PortBusyError(port, error)
    
    elif "failed to connect" in error_str or "sync failed" in error_str:
        return SyncError("ESP32-S2", error)
    
    elif "timeout" in error_str or "timed out" in error_str:
        return FlashTimeout(120, context or "operación", error)
    
    elif "checksum" in error_str or "verification" in error_str:
        return ChecksumMismatch("desconocido", "desconocido", error)
    
    elif "no serial data received" in error_str:
        return DeviceNotFoundError(None, error)
    
    elif "unsupported" in error_str or "not supported" in error_str:
        return UnsupportedDeviceError("desconocido", ["ESP32-S2"], error)
    
    elif "invalid" in error_str and "firmware" in error_str:
        return InvalidFirmwareError("Formato de archivo inválido", None, error)
    
    # Si no podemos mapear específicamente, usar FlashError genérico
    return FlashError(f"Error durante {context}: {error}", error)