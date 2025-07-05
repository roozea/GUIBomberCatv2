"""Detector de dispositivos BomberCat (ESP32-S2) multiplataforma.

Este módulo proporciona funcionalidad para detectar automáticamente
dispositivos ESP32-S2 en Windows, macOS y Linux usando esptool.py
y serial.tools.list_ports.
"""

import logging
from typing import Optional, List, Dict

import serial.tools.list_ports
from esptool.cmds import detect_chip


logger = logging.getLogger(__name__)


class DeviceDetector:
    """Detector de dispositivos ESP32-S2 multiplataforma."""
    
    # Chips soportados por el detector
    supported_chips = ["esp32-s2"]
    
    # VID/PID conocidos para dispositivos ESP32-S2
    ESP32_S2_VID_PID = [
        (0x303A, 0x0002),  # Espressif ESP32-S2
        (0x10C4, 0xEA60),  # Silicon Labs CP210x (común en dev boards)
        (0x1A86, 0x7523),  # QinHeng Electronics CH340
        (0x0403, 0x6001),  # FTDI FT232R
    ]
    
    def __init__(self):
        """Inicializa el detector de dispositivos."""
        logger.info("Inicializando detector de dispositivos BomberCat")
    
    def scan_ports(self) -> List[Dict[str, str]]:
        """Escanea puertos serie y devuelve lista de dispositivos ESP potenciales.
        
        Returns:
            Lista de diccionarios con 'port', 'description', 'hwid' para
            cada dispositivo ESP detectado.
        """
        logger.info("Escaneando puertos serie para dispositivos ESP32-S2")
        
        detected_devices = []
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            if self._is_esp_device(port):
                device_info = {
                    'port': port.device,
                    'description': port.description or 'Unknown',
                    'hwid': port.hwid or 'Unknown'
                }
                detected_devices.append(device_info)
                logger.debug(f"Dispositivo ESP detectado: {device_info}")
        
        logger.info(f"Se encontraron {len(detected_devices)} dispositivos ESP potenciales")
        return detected_devices
    
    def detect_chip(self, port: str) -> Optional[str]:
        """Detecta el tipo de chip ESP en el puerto especificado.
        
        Args:
            port: Puerto serie a verificar (ej: '/dev/ttyUSB0', 'COM3')
            
        Returns:
            Nombre del chip si es soportado, None en caso contrario.
        """
        logger.info(f"Detectando chip en puerto {port}")
        
        try:
            # Usar detect_chip de esptool.cmds con context manager
            with detect_chip(port) as esp:
                chip_name = esp.CHIP_NAME.lower()
                
                logger.debug(f"Chip detectado: {chip_name}")
                
                # Verificar si el chip está soportado
                if chip_name in self.supported_chips:
                    logger.info(f"Chip soportado encontrado: {chip_name} en {port}")
                    return chip_name
                else:
                    logger.warning(f"Chip no soportado: {chip_name} en {port}")
                    return None
                
        except Exception as e:
            logger.error(f"Error detectando chip en {port}: {e}")
            return None
    
    def _is_esp_device(self, port) -> bool:
        """Verifica si un puerto corresponde a un dispositivo ESP.
        
        Args:
            port: Objeto ComPort de serial.tools.list_ports
            
        Returns:
            True si el dispositivo parece ser un ESP, False en caso contrario.
        """
        # Verificar por VID/PID conocidos
        if hasattr(port, 'vid') and hasattr(port, 'pid'):
            if port.vid is not None and port.pid is not None:
                vid_pid = (port.vid, port.pid)
                if vid_pid in self.ESP32_S2_VID_PID:
                    logger.debug(f"Dispositivo ESP detectado por VID/PID: {vid_pid}")
                    return True
        
        # Verificar por descripción (fallback)
        description = (port.description or '').lower()
        esp_keywords = ['esp', 'silicon labs', 'cp210', 'ch340', 'ftdi']
        
        for keyword in esp_keywords:
            if keyword in description:
                logger.debug(f"Dispositivo ESP detectado por descripción: {description}")
                return True
        
        return False
    
    def get_verified_devices(self) -> List[Dict[str, str]]:
        """Obtiene lista de dispositivos ESP32-S2 verificados.
        
        Combina escaneo de puertos con detección de chip para
        devolver solo dispositivos ESP32-S2 confirmados.
        
        Returns:
            Lista de dispositivos verificados con información adicional del chip.
        """
        logger.info("Obteniendo dispositivos ESP32-S2 verificados")
        
        potential_devices = self.scan_ports()
        verified_devices = []
        
        for device in potential_devices:
            chip_type = self.detect_chip(device['port'])
            if chip_type:
                device['chip_type'] = chip_type
                verified_devices.append(device)
                logger.info(f"Dispositivo verificado: {device['port']} ({chip_type})")
        
        return verified_devices