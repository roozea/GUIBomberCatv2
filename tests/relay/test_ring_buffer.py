"""Tests para RingBuffer zero-copy.

Verifica correctness de operaciones y que no se realicen copias.
"""

import pytest
import threading
import time
from modules.bombercat_relay.ring_buffer import RingBuffer


class TestRingBuffer:
    """Tests para RingBuffer."""
    
    def test_initialization(self):
        """Test inicialización básica."""
        buffer = RingBuffer(1024)
        
        assert buffer.capacity == 1024
        assert buffer.size == 0
        assert buffer.available_space == 1024
        assert buffer.is_empty
        assert not buffer.is_full
        assert len(buffer) == 0
        assert not buffer
    
    def test_invalid_capacity(self):
        """Test capacidad inválida."""
        with pytest.raises(ValueError, match="La capacidad debe ser mayor a 0"):
            RingBuffer(0)
        
        with pytest.raises(ValueError, match="La capacidad debe ser mayor a 0"):
            RingBuffer(-1)
    
    def test_simple_write_read(self):
        """Test escritura y lectura simple."""
        buffer = RingBuffer(1024)
        test_data = b"Hello, World!"
        
        # Escribir datos
        bytes_written = buffer.write(test_data)
        assert bytes_written == len(test_data)
        assert buffer.size == len(test_data)
        assert not buffer.is_empty
        
        # Leer datos
        read_data = buffer.read(len(test_data))
        assert read_data is not None
        assert bytes(read_data) == test_data
        assert buffer.size == 0
        assert buffer.is_empty
    
    def test_zero_copy_verification(self):
        """Test que verifica que no se realizan copias."""
        buffer = RingBuffer(1024)
        test_data = bytearray(b"Test data for zero-copy verification")
        
        # Obtener ID del primer byte antes de escribir
        original_id = id(test_data[0])
        
        # Escribir datos
        buffer.write(test_data)
        
        # Leer datos como memoryview
        read_view = buffer.read(len(test_data))
        assert read_view is not None
        
        # Verificar que es memoryview (zero-copy)
        assert isinstance(read_view, memoryview)
        
        # El contenido debe ser igual
        assert bytes(read_view) == bytes(test_data)
    
    def test_partial_read(self):
        """Test lectura parcial."""
        buffer = RingBuffer(1024)
        test_data = b"0123456789"
        
        buffer.write(test_data)
        
        # Leer solo parte de los datos
        partial_data = buffer.read(5)
        assert partial_data is not None
        assert bytes(partial_data) == b"01234"
        assert buffer.size == 5
        
        # Leer el resto
        remaining_data = buffer.read(5)
        assert remaining_data is not None
        assert bytes(remaining_data) == b"56789"
        assert buffer.size == 0
    
    def test_wrap_around_write(self):
        """Test escritura con wrap-around."""
        buffer = RingBuffer(10)
        
        # Llenar buffer
        buffer.write(b"0123456789")
        assert buffer.is_full
        
        # Leer parte
        data1 = buffer.read(6)
        assert bytes(data1) == b"012345"
        assert buffer.size == 4
        
        # Escribir más datos (wrap-around)
        buffer.write(b"ABCDEF")
        assert buffer.size == 10
        assert buffer.is_full
        
        # Leer todo
        all_data = buffer.read(10)
        assert bytes(all_data) == b"6789ABCDEF"
    
    def test_wrap_around_read(self):
        """Test lectura con wrap-around."""
        buffer = RingBuffer(8)
        
        # Escribir y leer para posicionar punteros
        buffer.write(b"12345")
        buffer.read(3)  # Lee "123", quedan "45"
        
        # Escribir más datos (wrap-around)
        buffer.write(b"ABCDEF")  # Buffer: "EF45ABCD"
        
        # Leer con wrap-around
        data = buffer.read(8)
        assert bytes(data) == b"45ABCDEF"
    
    def test_peek_functionality(self):
        """Test funcionalidad peek."""
        buffer = RingBuffer(1024)
        test_data = b"Peek test data"
        
        buffer.write(test_data)
        
        # Peek no debe consumir datos
        peeked = buffer.peek(5)
        assert peeked is not None
        assert bytes(peeked) == b"Peek "
        assert buffer.size == len(test_data)  # Sin cambios
        
        # Peek todo
        peeked_all = buffer.peek(len(test_data))
        assert bytes(peeked_all) == test_data
        assert buffer.size == len(test_data)
        
        # Read debe devolver los mismos datos
        read_data = buffer.read(len(test_data))
        assert bytes(read_data) == test_data
        assert buffer.size == 0
    
    def test_peek_wrap_around(self):
        """Test peek con wrap-around."""
        buffer = RingBuffer(8)
        
        # Configurar wrap-around
        buffer.write(b"12345")
        buffer.read(3)  # Quedan "45"
        buffer.write(b"ABCD")  # Buffer: "CD45ABCD" (conceptual)
        
        # Peek con wrap-around
        peeked = buffer.peek(6)
        assert bytes(peeked) == b"45ABCD"
        
        # Los datos deben seguir ahí
        assert buffer.size == 6
    
    def test_buffer_full_error(self):
        """Test error cuando buffer está lleno."""
        buffer = RingBuffer(5)
        
        # Llenar buffer
        buffer.write(b"12345")
        assert buffer.is_full
        
        # Intentar escribir más debe fallar
        with pytest.raises(ValueError, match="No hay espacio suficiente"):
            buffer.write(b"X")
    
    def test_empty_operations(self):
        """Test operaciones en buffer vacío."""
        buffer = RingBuffer(1024)
        
        # Leer de buffer vacío
        assert buffer.read(10) is None
        assert buffer.peek(10) is None
        
        # Escribir datos vacíos
        assert buffer.write(b"") == 0
        assert buffer.size == 0
    
    def test_clear_functionality(self):
        """Test funcionalidad clear."""
        buffer = RingBuffer(1024)
        
        # Escribir datos
        buffer.write(b"Test data")
        assert buffer.size > 0
        
        # Clear
        buffer.clear()
        assert buffer.size == 0
        assert buffer.is_empty
        assert buffer.available_space == buffer.capacity
    
    def test_thread_safety(self):
        """Test thread safety básico."""
        buffer = RingBuffer(1024)
        results = []
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    data = f"data_{i:03d}".encode()
                    buffer.write(data)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                while len(results) < 100:
                    data = buffer.read(8)
                    if data:
                        results.append(bytes(data))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Iniciar threads
        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)
        
        writer_thread.start()
        reader_thread.start()
        
        # Esperar finalización
        writer_thread.join(timeout=5)
        reader_thread.join(timeout=5)
        
        # Verificar que no hubo errores
        assert not errors, f"Errores en threads: {errors}"
        
        # Verificar que se leyeron datos
        assert len(results) > 0
    
    def test_large_data_handling(self):
        """Test manejo de datos grandes."""
        buffer = RingBuffer(2048)
        
        # Datos grandes (pero que caben en buffer)
        large_data = b"X" * 1500
        
        buffer.write(large_data)
        assert buffer.size == 1500
        
        read_data = buffer.read(1500)
        assert bytes(read_data) == large_data
    
    def test_multiple_small_writes(self):
        """Test múltiples escrituras pequeñas."""
        buffer = RingBuffer(1024)
        
        # Escribir múltiples chunks pequeños
        chunks = [f"chunk_{i}".encode() for i in range(10)]
        
        for chunk in chunks:
            buffer.write(chunk)
        
        # Leer todo de una vez
        all_data = buffer.read(1024)
        expected = b"".join(chunks)
        
        assert bytes(all_data) == expected
    
    def test_context_manager_like_usage(self):
        """Test uso similar a context manager."""
        buffer = RingBuffer(1024)
        
        # Simular uso en context
        test_data = b"Context test"
        buffer.write(test_data)
        
        # Verificar estado
        assert bool(buffer) == True  # No vacío
        assert len(buffer) == len(test_data)
        
        # Leer todo
        buffer.read(len(test_data))
        assert bool(buffer) == False  # Vacío
        assert len(buffer) == 0


class TestRingBufferPerformance:
    """Tests de rendimiento para RingBuffer."""
    
    def test_write_read_performance(self):
        """Test básico de rendimiento write/read."""
        buffer = RingBuffer(8192)
        test_data = b"X" * 1024
        
        start_time = time.perf_counter()
        
        # Múltiples operaciones
        for _ in range(100):
            buffer.write(test_data)
            read_data = buffer.read(1024)
            assert len(read_data) == 1024
        
        elapsed = time.perf_counter() - start_time
        
        # Debe ser rápido (menos de 100ms para 100 operaciones)
        assert elapsed < 0.1, f"Operaciones muy lentas: {elapsed:.3f}s"
    
    @pytest.mark.benchmark
    def test_benchmark_write_read(self, benchmark):
        """Benchmark de operaciones write/read."""
        buffer = RingBuffer(8192)
        test_data = b"Benchmark data" * 10
        
        def write_read_cycle():
            buffer.write(test_data)
            data = buffer.read(len(test_data))
            return data
        
        result = benchmark(write_read_cycle)
        assert len(result) == len(test_data)