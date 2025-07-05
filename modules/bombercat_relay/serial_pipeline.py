"""Pipeline Serial Optimizado para NFC Relay

Implementa canal serie de alta velocidad con operaciones no bloqueantes.
Optimizado para latencia mínima y máximo throughput.
"""

import asyncio
import threading
import time
from typing import Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

import serial
from serial.tools import list_ports

from modules.bombercat_relay.ring_buffer import RingBuffer


class PipelineState(Enum):
    """Estados del pipeline serial."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class SerialConfig:
    """Configuración del puerto serie."""
    port: str
    baudrate: int = 921600
    timeout: float = 0.001  # 1ms timeout
    write_timeout: float = 0.001
    bytesize: int = serial.EIGHTBITS
    parity: str = serial.PARITY_NONE
    stopbits: int = serial.STOPBITS_ONE
    rtscts: bool = False
    dsrdtr: bool = False
    xonxoff: bool = False
    
    def to_serial_kwargs(self) -> dict:
        """Convierte a argumentos para pyserial."""
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'timeout': self.timeout,
            'write_timeout': self.write_timeout,
            'bytesize': self.bytesize,
            'parity': self.parity,
            'stopbits': self.stopbits,
            'rtscts': self.rtscts,
            'dsrdtr': self.dsrdtr,
            'xonxoff': self.xonxoff
        }


class SerialPipeline:
    """Pipeline serie optimizado para NFC relay.
    
    Maneja lectura/escritura no bloqueante con buffers zero-copy.
    Diseñado para latencia mínima y alta velocidad.
    """
    
    def __init__(self, 
                 rx_config: SerialConfig,
                 tx_config: SerialConfig,
                 rx_buffer: Optional[RingBuffer] = None,
                 tx_buffer: Optional[RingBuffer] = None,
                 buffer_size: int = 8192):
        """Inicializa el pipeline serial.
        
        Args:
            rx_config: Configuración puerto de recepción
            tx_config: Configuración puerto de transmisión  
            rx_buffer: Buffer de recepción (se crea si es None)
            tx_buffer: Buffer de transmisión (se crea si es None)
            buffer_size: Tamaño de buffers por defecto
        """
        self.rx_config = rx_config
        self.tx_config = tx_config
        
        # Buffers
        self.rx_buffer = rx_buffer or RingBuffer(buffer_size)
        self.tx_buffer = tx_buffer or RingBuffer(buffer_size)
        
        # Puertos serie
        self.rx_serial: Optional[serial.Serial] = None
        self.tx_serial: Optional[serial.Serial] = None
        
        # Control de estado
        self._state = PipelineState.STOPPED
        self._state_lock = threading.RLock()
        
        # Threads de trabajo
        self._rx_thread: Optional[threading.Thread] = None
        self._tx_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self.on_data_received: Optional[Callable[[bytes], None]] = None
        self.on_data_sent: Optional[Callable[[int], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # Estadísticas
        self.stats = {
            'bytes_received': 0,
            'bytes_sent': 0,
            'rx_errors': 0,
            'tx_errors': 0,
            'reconnections': 0,
            'last_activity': 0
        }
    
    @property
    def state(self) -> PipelineState:
        """Estado actual del pipeline."""
        with self._state_lock:
            return self._state
    
    @property
    def is_running(self) -> bool:
        """True si el pipeline está ejecutándose."""
        return self.state == PipelineState.RUNNING
    
    @property
    def is_connected(self) -> bool:
        """True si ambos puertos están conectados."""
        return (self.rx_serial is not None and self.rx_serial.is_open and
                self.tx_serial is not None and self.tx_serial.is_open)
    
    def start(self) -> bool:
        """Inicia el pipeline serial.
        
        Returns:
            True si se inició correctamente
        """
        with self._state_lock:
            if self._state != PipelineState.STOPPED:
                return False
            
            self._state = PipelineState.STARTING
        
        try:
            # Abrir puertos serie
            self._open_serial_ports()
            
            # Limpiar buffers
            self.rx_buffer.clear()
            self.tx_buffer.clear()
            
            # Iniciar threads
            self._stop_event.clear()
            self._start_threads()
            
            with self._state_lock:
                self._state = PipelineState.RUNNING
            
            return True
            
        except Exception as e:
            with self._state_lock:
                self._state = PipelineState.ERROR
            
            if self.on_error:
                self.on_error(e)
            
            self._cleanup()
            return False
    
    def stop(self) -> None:
        """Detiene el pipeline serial."""
        with self._state_lock:
            if self._state in [PipelineState.STOPPED, PipelineState.STOPPING]:
                return
            
            self._state = PipelineState.STOPPING
        
        # Señalar parada
        self._stop_event.set()
        
        # Esperar threads
        self._join_threads()
        
        # Limpiar recursos
        self._cleanup()
        
        with self._state_lock:
            self._state = PipelineState.STOPPED
    
    def write(self, data: bytes) -> int:
        """Escribe datos al buffer de transmisión.
        
        Args:
            data: Datos a enviar
            
        Returns:
            Número de bytes escritos
        """
        if not self.is_running:
            return 0
        
        try:
            return self.tx_buffer.write(data)
        except ValueError:
            # Buffer lleno
            return 0
    
    def read(self, max_bytes: int = 1024) -> Optional[bytes]:
        """Lee datos del buffer de recepción.
        
        Args:
            max_bytes: Máximo número de bytes a leer
            
        Returns:
            Datos leídos o None si no hay datos
        """
        if not self.is_running:
            return None
        
        data_view = self.rx_buffer.read(max_bytes)
        if data_view:
            return bytes(data_view)
        return None
    
    def peek(self, max_bytes: int = 1024) -> Optional[bytes]:
        """Mira datos sin consumirlos del buffer.
        
        Args:
            max_bytes: Máximo número de bytes a mirar
            
        Returns:
            Datos disponibles o None
        """
        data_view = self.rx_buffer.peek(max_bytes)
        if data_view:
            return bytes(data_view)
        return None
    
    def flush_tx(self) -> None:
        """Fuerza el envío de datos pendientes."""
        if self.tx_serial and self.tx_serial.is_open:
            try:
                self.tx_serial.flush()
            except serial.SerialException:
                pass
    
    def _open_serial_ports(self) -> None:
        """Abre los puertos serie."""
        # Puerto RX
        self.rx_serial = serial.Serial(**self.rx_config.to_serial_kwargs())
        
        # Puerto TX (puede ser el mismo que RX)
        if self.tx_config.port == self.rx_config.port:
            self.tx_serial = self.rx_serial
        else:
            self.tx_serial = serial.Serial(**self.tx_config.to_serial_kwargs())
        
        # Configurar buffers del SO
        if hasattr(self.rx_serial, 'set_buffer_size'):
            self.rx_serial.set_buffer_size(rx_size=8192, tx_size=8192)
        
        if self.tx_serial != self.rx_serial and hasattr(self.tx_serial, 'set_buffer_size'):
            self.tx_serial.set_buffer_size(rx_size=8192, tx_size=8192)
    
    def _start_threads(self) -> None:
        """Inicia los threads de trabajo."""
        self._rx_thread = threading.Thread(
            target=self._rx_worker,
            name="SerialPipeline-RX",
            daemon=True
        )
        
        self._tx_thread = threading.Thread(
            target=self._tx_worker,
            name="SerialPipeline-TX", 
            daemon=True
        )
        
        self._rx_thread.start()
        self._tx_thread.start()
    
    def _rx_worker(self) -> None:
        """Worker thread para recepción de datos."""
        temp_buffer = bytearray(1024)
        
        while not self._stop_event.is_set():
            try:
                if not self.rx_serial or not self.rx_serial.is_open:
                    break
                
                # Leer datos disponibles
                bytes_available = self.rx_serial.in_waiting
                if bytes_available > 0:
                    bytes_to_read = min(bytes_available, len(temp_buffer))
                    bytes_read = self.rx_serial.readinto(temp_buffer[:bytes_to_read])
                    
                    if bytes_read > 0:
                        data = temp_buffer[:bytes_read]
                        
                        # Escribir al buffer
                        try:
                            self.rx_buffer.write(data)
                            self.stats['bytes_received'] += bytes_read
                            self.stats['last_activity'] = time.time()
                            
                            # Callback
                            if self.on_data_received:
                                self.on_data_received(bytes(data))
                                
                        except ValueError:
                            # Buffer lleno - descartar datos más antiguos
                            self.rx_buffer.clear()
                            self.rx_buffer.write(data)
                
                else:
                    # No hay datos - dormir brevemente
                    time.sleep(0.0001)  # 0.1ms
                    
            except serial.SerialException as e:
                self.stats['rx_errors'] += 1
                if self.on_error:
                    self.on_error(e)
                break
            
            except Exception as e:
                self.stats['rx_errors'] += 1
                if self.on_error:
                    self.on_error(e)
    
    def _tx_worker(self) -> None:
        """Worker thread para transmisión de datos."""
        while not self._stop_event.is_set():
            try:
                if not self.tx_serial or not self.tx_serial.is_open:
                    break
                
                # Leer datos del buffer
                data_view = self.tx_buffer.read(1024)
                if data_view:
                    data = bytes(data_view)
                    
                    # Enviar datos
                    bytes_written = self.tx_serial.write(data)
                    
                    if bytes_written > 0:
                        self.stats['bytes_sent'] += bytes_written
                        self.stats['last_activity'] = time.time()
                        
                        # Callback
                        if self.on_data_sent:
                            self.on_data_sent(bytes_written)
                
                else:
                    # No hay datos - dormir brevemente
                    time.sleep(0.0001)  # 0.1ms
                    
            except serial.SerialException as e:
                self.stats['tx_errors'] += 1
                if self.on_error:
                    self.on_error(e)
                break
            
            except Exception as e:
                self.stats['tx_errors'] += 1
                if self.on_error:
                    self.on_error(e)
    
    def _join_threads(self) -> None:
        """Espera a que terminen los threads."""
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        
        if self._tx_thread and self._tx_thread.is_alive():
            self._tx_thread.join(timeout=1.0)
    
    def _cleanup(self) -> None:
        """Limpia recursos."""
        # Cerrar puertos
        if self.rx_serial and self.rx_serial.is_open:
            try:
                self.rx_serial.close()
            except Exception:
                pass
        
        if (self.tx_serial and 
            self.tx_serial != self.rx_serial and 
            self.tx_serial.is_open):
            try:
                self.tx_serial.close()
            except Exception:
                pass
        
        self.rx_serial = None
        self.tx_serial = None
        self._rx_thread = None
        self._tx_thread = None


def list_serial_ports() -> list[str]:
    """Lista puertos serie disponibles.
    
    Returns:
        Lista de nombres de puertos
    """
    return [port.device for port in list_ports.comports()]


def find_nfc_ports() -> list[str]:
    """Busca puertos que podrían ser dispositivos NFC.
    
    Returns:
        Lista de puertos candidatos
    """
    candidates = []
    
    for port in list_ports.comports():
        # Buscar por descripción/fabricante
        description = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        
        nfc_keywords = ['nfc', 'pn532', 'acr122', 'proxmark', 'chameleon']
        
        if any(keyword in description or keyword in manufacturer 
               for keyword in nfc_keywords):
            candidates.append(port.device)
    
    return candidates