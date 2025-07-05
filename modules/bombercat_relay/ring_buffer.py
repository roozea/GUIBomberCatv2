"""Ring Buffer Zero-Copy para NFC Relay

Implementación de buffer circular sin copias usando memoryview.
Optimizado para alta velocidad y baja latencia.
"""

import threading
from typing import Optional


class RingBuffer:
    """Buffer circular zero-copy thread-safe.
    
    Usa memoryview para evitar copias de datos y maximizar rendimiento.
    Ideal para streaming de datos APDU a alta velocidad.
    """
    
    def __init__(self, capacity: int):
        """Inicializa el ring buffer.
        
        Args:
            capacity: Tamaño máximo del buffer en bytes
        """
        if capacity <= 0:
            raise ValueError("La capacidad debe ser mayor a 0")
            
        self._buffer = bytearray(capacity)
        self._memory = memoryview(self._buffer)
        self._capacity = capacity
        self._head = 0  # Posición de escritura
        self._tail = 0  # Posición de lectura
        self._size = 0  # Bytes disponibles para leer
        self._lock = threading.RLock()
    
    @property
    def capacity(self) -> int:
        """Capacidad total del buffer."""
        return self._capacity
    
    @property
    def size(self) -> int:
        """Bytes disponibles para leer."""
        with self._lock:
            return self._size
    
    @property
    def available_space(self) -> int:
        """Espacio disponible para escribir."""
        with self._lock:
            return self._capacity - self._size
    
    @property
    def is_empty(self) -> bool:
        """True si el buffer está vacío."""
        with self._lock:
            return self._size == 0
    
    @property
    def is_full(self) -> bool:
        """True si el buffer está lleno."""
        with self._lock:
            return self._size == self._capacity
    
    def write(self, data: bytes) -> int:
        """Escribe datos al buffer sin copiar.
        
        Args:
            data: Datos a escribir
            
        Returns:
            Número de bytes escritos
            
        Raises:
            ValueError: Si no hay espacio suficiente
        """
        if not data:
            return 0
            
        data_len = len(data)
        
        with self._lock:
            if data_len > self.available_space:
                raise ValueError(f"No hay espacio suficiente: {data_len} > {self.available_space}")
            
            # Escribir datos usando memoryview (zero-copy)
            if self._head + data_len <= self._capacity:
                # Escritura simple sin wrap-around
                self._memory[self._head:self._head + data_len] = data
            else:
                # Escritura con wrap-around
                first_chunk = self._capacity - self._head
                self._memory[self._head:] = data[:first_chunk]
                self._memory[:data_len - first_chunk] = data[first_chunk:]
            
            self._head = (self._head + data_len) % self._capacity
            self._size += data_len
            
            return data_len
    
    def read(self, n: int) -> Optional[memoryview]:
        """Lee datos del buffer sin copiar.
        
        Args:
            n: Número máximo de bytes a leer
            
        Returns:
            memoryview con los datos leídos o None si no hay datos
        """
        if n <= 0:
            return None
            
        with self._lock:
            if self._size == 0:
                return None
            
            # Leer solo los bytes disponibles
            bytes_to_read = min(n, self._size)
            
            if self._tail + bytes_to_read <= self._capacity:
                # Lectura simple sin wrap-around
                result = self._memory[self._tail:self._tail + bytes_to_read]
            else:
                # Lectura con wrap-around - necesitamos crear un nuevo buffer
                first_chunk = self._capacity - self._tail
                second_chunk = bytes_to_read - first_chunk
                
                # Crear buffer temporal para datos fragmentados
                temp_buffer = bytearray(bytes_to_read)
                temp_buffer[:first_chunk] = self._memory[self._tail:]
                temp_buffer[first_chunk:] = self._memory[:second_chunk]
                result = memoryview(temp_buffer)
            
            self._tail = (self._tail + bytes_to_read) % self._capacity
            self._size -= bytes_to_read
            
            return result
    
    def peek(self, n: int) -> Optional[memoryview]:
        """Mira datos sin consumirlos del buffer.
        
        Args:
            n: Número máximo de bytes a mirar
            
        Returns:
            memoryview con los datos o None si no hay datos
        """
        if n <= 0:
            return None
            
        with self._lock:
            if self._size == 0:
                return None
            
            bytes_to_peek = min(n, self._size)
            
            if self._tail + bytes_to_peek <= self._capacity:
                return self._memory[self._tail:self._tail + bytes_to_peek]
            else:
                # Para peek con wrap-around, crear buffer temporal
                first_chunk = self._capacity - self._tail
                second_chunk = bytes_to_peek - first_chunk
                
                temp_buffer = bytearray(bytes_to_peek)
                temp_buffer[:first_chunk] = self._memory[self._tail:]
                temp_buffer[first_chunk:] = self._memory[:second_chunk]
                return memoryview(temp_buffer)
    
    def clear(self) -> None:
        """Limpia el buffer."""
        with self._lock:
            self._head = 0
            self._tail = 0
            self._size = 0
    
    def __len__(self) -> int:
        """Retorna el número de bytes disponibles para leer."""
        return self.size
    
    def __bool__(self) -> bool:
        """True si el buffer no está vacío."""
        return not self.is_empty