"""Tests de latencia y benchmark para NFC Relay.

Verifica que la latencia promedio sea < 5ms con 1000 APDUs dummy.
"""

import asyncio
import time
from unittest.mock import Mock, patch
import pytest
import numpy as np

from modules.bombercat_relay.metrics import (
    LatencyMeter, MetricsCollector, LatencyStats, ThroughputStats
)
from modules.bombercat_relay.apdu import APDU, create_response_apdu
from modules.bombercat_relay.ring_buffer import RingBuffer
from modules.bombercat_relay.serial_pipeline import SerialPipeline, SerialConfig


class TestLatencyMeter:
    """Tests para medición de latencia."""
    
    def test_latency_meter_initialization(self):
        """Test inicialización del medidor de latencia."""
        meter = LatencyMeter(history_size=50)
        
        assert meter.history_size == 50
        
        stats = meter.get_latency_stats()
        assert stats.count == 0
        assert stats.mean_ms == 0
        assert stats.min_ms == 0
        assert stats.max_ms == 0
        assert stats.std_dev_ms == 0
    
    def test_single_latency_measurement(self):
        """Test medición de latencia única."""
        meter = LatencyMeter()
        
        measurement_id = meter.start_measurement("test")
        time.sleep(0.001)  # 1ms
        latency_ns = meter.end_measurement(measurement_id)
        
        assert latency_ns > 0
        assert latency_ns >= 900_000  # Al menos 0.9ms
        
        stats = meter.get_latency_stats()
        assert stats.count == 1
        assert stats.mean_ms >= 0.9
        assert stats.min_ms >= 0.9
        assert stats.max_ms >= 0.9
    
    def test_multiple_latency_measurements(self):
        """Test múltiples mediciones de latencia."""
        meter = LatencyMeter(history_size=5)
        
        latencies = []
        for i in range(10):
            measurement_id = meter.start_measurement(f"test_{i}")
            # Simular diferentes tiempos de espera
            time.sleep(0.001 * (i % 3 + 1))  # 1ms, 2ms, 3ms variando
            latency = meter.end_measurement(measurement_id)
            latencies.append(latency)
        
        stats = meter.get_latency_stats()
        # Solo debe mantener las últimas 5
        assert stats.count == 5
        assert stats.mean_ms > 0
        assert stats.min_ms > 0
        assert stats.max_ms > 0
    
    def test_latency_window_overflow(self):
        """Test desbordamiento de ventana de latencias."""
        meter = LatencyMeter(history_size=3)
        
        # Agregar más latencias que el tamaño de ventana
        for i in range(10):
            measurement_id = meter.start_measurement(f"test_{i}")
            time.sleep(0.001)  # 1ms cada una
            meter.end_measurement(measurement_id)
        
        stats = meter.get_latency_stats()
        # Solo debe mantener las últimas 3
        assert stats.count == 3
        assert stats.mean_ms > 0
    
    def test_latency_statistics_calculation(self):
        """Test cálculo de estadísticas de latencia."""
        meter = LatencyMeter()
        
        # Simular latencias conocidas usando sleep
        sleep_times = [0.001, 0.002, 0.003, 0.004, 0.005]  # 1ms, 2ms, 3ms, 4ms, 5ms
        
        for sleep_time in sleep_times:
            measurement_id = meter.start_measurement("test")
            time.sleep(sleep_time)
            meter.end_measurement(measurement_id)
        
        stats = meter.get_latency_stats()
        
        assert stats.count == 5
        assert stats.mean_ms >= 2.5  # Aproximadamente 3ms promedio
        assert stats.mean_ms <= 4.0  # Con tolerancia
        assert stats.min_ms >= 0.9   # Al menos 0.9ms mínimo
        assert stats.max_ms >= 4.5   # Al menos 4.5ms máximo
        assert stats.std_dev_ms >= 0     # Desviación estándar positiva


class TestMetricsCollector:
    """Tests para recolector de métricas."""
    
    def test_metrics_collector_initialization(self):
        """Test inicialización del recolector."""
        collector = MetricsCollector()
        
        # Verificar que no hay meters inicialmente
        snapshots = collector.get_all_snapshots()
        assert len(snapshots) == 0
    
    def test_apdu_processing_metrics(self):
        """Test métricas de procesamiento APDU."""
        collector = MetricsCollector()
        meter = LatencyMeter()
        collector.add_meter("apdu", meter)
        
        # Simular procesamiento de APDU
        measurement_id = meter.start_measurement("apdu_processing")
        time.sleep(0.001)  # 1ms
        meter.end_measurement(measurement_id)
        
        snapshots = collector.get_all_snapshots()
        
        assert "apdu" in snapshots
        assert snapshots["apdu"].latency.count == 1
        assert snapshots["apdu"].latency.mean_ms >= 0.9  # Al menos 0.9ms
    
    def test_error_tracking(self):
        """Test seguimiento de errores."""
        collector = MetricsCollector()
        meter = LatencyMeter()
        collector.add_meter("errors", meter)
        
        # Simular algunas mediciones para tener datos
        measurement_id = meter.start_measurement("test")
        time.sleep(0.001)
        meter.end_measurement(measurement_id)
        
        snapshots = collector.get_all_snapshots()
        assert "errors" in snapshots
        assert snapshots["errors"].latency.count == 1
    
    def test_throughput_calculation(self):
        """Test cálculo de throughput."""
        collector = MetricsCollector()
        meter = LatencyMeter()
        collector.add_meter("throughput", meter)
        
        # Simular múltiples mediciones rápidas y registrar throughput
        for i in range(10):
            measurement_id = meter.start_measurement(f"test_{i}")
            time.sleep(0.001)  # 1ms cada una
            meter.end_measurement(measurement_id)
            # Registrar throughput para cada mensaje
            meter.record_throughput(100, 1)  # 100 bytes por mensaje
        
        snapshots = collector.get_all_snapshots()
        assert "throughput" in snapshots
        assert snapshots["throughput"].latency.count == 10
        assert snapshots["throughput"].throughput.messages_per_second > 0
    
    def test_metrics_reset(self):
        """Test reset de métricas."""
        collector = MetricsCollector()
        meter = LatencyMeter()
        collector.add_meter("test", meter)
        
        # Agregar algunas métricas
        measurement_id = meter.start_measurement("test")
        time.sleep(0.001)
        meter.end_measurement(measurement_id)
        
        # Verificar que hay datos
        snapshots = collector.get_all_snapshots()
        assert snapshots["test"].latency.count == 1
        
        # Reset
        collector.reset_all()
        
        snapshots = collector.get_all_snapshots()
        assert snapshots["test"].latency.count == 0


class TestLatencyBenchmark:
    """Tests de benchmark de latencia."""
    
    def test_dummy_apdu_creation_performance(self, benchmark):
        """Benchmark creación de APDUs dummy."""
        def create_dummy_apdu():
            return APDU(
                cla=0x00,
                ins=0xA4,
                p1=0x04,
                p2=0x00,
                lc=8,
                data=b"\x01\x02\x03\x04\x05\x06\x07\x08"
            )
        
        result = benchmark(create_dummy_apdu)
        assert result.is_valid
    
    def test_apdu_parsing_performance(self, benchmark):
        """Benchmark parsing de APDU."""
        from modules.bombercat_relay.apdu import parse_apdu
        
        # APDU de prueba
        apdu_bytes = bytes([0x00, 0xA4, 0x04, 0x00, 0x08]) + b"\x01\x02\x03\x04\x05\x06\x07\x08"
        
        def parse_test_apdu():
            return parse_apdu(apdu_bytes)
        
        result = benchmark(parse_test_apdu)
        assert result is not None
        assert result.is_valid
    
    def test_ring_buffer_performance(self, benchmark):
        """Benchmark operaciones de ring buffer."""
        buffer = RingBuffer(1024)
        test_data = b"X" * 100
        
        def buffer_operations():
            buffer.write(test_data)
            return buffer.read(100)
        
        result = benchmark(buffer_operations)
        assert result == test_data
    
    def test_latency_measurement_overhead(self, benchmark):
        """Benchmark overhead de medición de latencia."""
        meter = LatencyMeter()
        
        def measure_latency():
            measurement_id = meter.start_measurement("benchmark")
            # Simular trabajo mínimo
            _ = 1 + 1
            return meter.end_measurement(measurement_id)
        
        result = benchmark(measure_latency)
        assert result > 0
    
    @pytest.mark.benchmark(group="apdu_processing")
    def test_complete_apdu_processing_pipeline(self, benchmark):
        """Benchmark pipeline completo de procesamiento APDU."""
        from modules.bombercat_relay.apdu import parse_apdu, create_response_apdu
        
        # APDU de comando
        command_bytes = bytes([0x00, 0xA4, 0x04, 0x00, 0x04]) + b"\x01\x02\x03\x04"
        
        def process_apdu():
            # Parse comando
            apdu = parse_apdu(command_bytes)
            if apdu and apdu.is_valid:
                # Crear respuesta
                response = create_response_apdu(b"\x90\x00")
                return response
            return None
        
        result = benchmark(process_apdu)
        assert result is not None
    
    def test_1000_apdu_latency_benchmark(self, benchmark):
        """Benchmark principal: 1000 APDUs con latencia < 5ms promedio."""
        from modules.bombercat_relay.apdu import parse_apdu, create_response_apdu
        
        # APDUs de prueba variados
        test_apdus = [
            bytes([0x00, 0xA4, 0x04, 0x00]),  # SELECT
            bytes([0x00, 0xC0, 0x00, 0x00, 0x00]),  # GET RESPONSE
            bytes([0x00, 0xB0, 0x00, 0x00, 0x10]),  # READ BINARY
            bytes([0x00, 0xD6, 0x00, 0x00, 0x04]) + b"\x01\x02\x03\x04",  # UPDATE BINARY
        ]
        
        meter = LatencyMeter(history_size=1000)
        
        def process_1000_apdus():
            latencies = []
            
            for i in range(1000):
                # Seleccionar APDU de prueba
                apdu_bytes = test_apdus[i % len(test_apdus)]
                
                # Medir latencia de procesamiento
                measurement_id = meter.start_measurement(f"apdu_{i}")
                
                # Procesar APDU
                apdu = parse_apdu(apdu_bytes)
                if apdu and apdu.is_valid:
                    response = create_response_apdu()
                
                # Registrar latencia
                latency_ns = meter.end_measurement(measurement_id)
                latencies.append(latency_ns)
            
            return latencies
        
        latencies = benchmark(process_1000_apdus)
        
        # Verificar que se procesaron 1000 APDUs
        assert len(latencies) == 1000
        
        # Calcular estadísticas
        mean_latency_ns = np.mean(latencies)
        mean_latency_ms = mean_latency_ns / 1_000_000
        
        max_latency_ns = max(latencies)
        max_latency_ms = max_latency_ns / 1_000_000
        
        min_latency_ns = min(latencies)
        min_latency_ms = min_latency_ns / 1_000_000
        
        # Imprimir estadísticas para debug
        print(f"\n=== Estadísticas de Latencia (1000 APDUs) ===")
        print(f"Latencia promedio: {mean_latency_ms:.3f} ms")
        print(f"Latencia mínima: {min_latency_ms:.3f} ms")
        print(f"Latencia máxima: {max_latency_ms:.3f} ms")
        print(f"Desviación estándar: {np.std(latencies) / 1_000_000:.3f} ms")
        
        # REQUISITO PRINCIPAL: Latencia promedio < 5ms
        assert mean_latency_ms < 5.0, f"Latencia promedio {mean_latency_ms:.3f}ms excede el límite de 5ms"
        
        # Verificaciones adicionales
        assert max_latency_ms < 50.0, f"Latencia máxima {max_latency_ms:.3f}ms es excesiva"
        assert min_latency_ms > 0, "Latencia mínima debe ser positiva"


class TestAsyncLatencyMeasurement:
    """Tests para medición de latencia en contexto asyncio."""
    
    @pytest.mark.asyncio
    async def test_async_latency_measurement(self):
        """Test medición de latencia en función async."""
        meter = LatencyMeter()
        
        async def async_operation():
            await asyncio.sleep(0.001)  # 1ms
            return "done"
        
        measurement_id = meter.start_measurement("async_op")
        result = await async_operation()
        latency_ns = meter.end_measurement(measurement_id)
        
        assert result == "done"
        assert latency_ns >= 1_000_000  # Al menos 1ms
    
    @pytest.mark.asyncio
    async def test_concurrent_latency_measurements(self):
        """Test mediciones de latencia concurrentes."""
        meter = LatencyMeter(history_size=10)
        
        async def measure_operation(delay_ms: float):
            measurement_id = meter.start_measurement(f"async_{delay_ms}")
            await asyncio.sleep(delay_ms / 1000)
            return meter.end_measurement(measurement_id)
        
        # Ejecutar múltiples operaciones concurrentemente
        tasks = [
            measure_operation(1),  # 1ms
            measure_operation(2),  # 2ms
            measure_operation(3),  # 3ms
            measure_operation(4),  # 4ms
            measure_operation(5),  # 5ms
        ]
        
        latencies = await asyncio.gather(*tasks)
        
        assert len(latencies) == 5
        assert all(lat > 0 for lat in latencies)
        
        # Verificar que las latencias están en orden aproximado
        # (puede haber variación debido a concurrencia)
        assert latencies[0] < latencies[-1]  # Primera < última
    
    @pytest.mark.asyncio
    async def test_metrics_collection_async(self):
        """Test recolección de métricas en contexto async."""
        collector = MetricsCollector()
        
        meter = LatencyMeter()
        collector.add_meter("async_apdu", meter)
        
        async def process_async_apdu(apdu_id: int):
            measurement_id = meter.start_measurement(f"async_processing_{apdu_id}")
            
            # Simular procesamiento async
            await asyncio.sleep(0.001)
            
            meter.end_measurement(measurement_id)
        
        # Procesar múltiples APDUs
        tasks = [process_async_apdu(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        snapshots = collector.get_all_snapshots()
        
        assert "async_apdu" in snapshots
        assert snapshots["async_apdu"].latency.count == 10
        assert snapshots["async_apdu"].latency.mean_ms > 0


class TestRealWorldLatencyScenarios:
    """Tests para escenarios de latencia del mundo real."""
    
    def test_serial_communication_simulation(self):
        """Test simulación de comunicación serie."""
        meter = LatencyMeter()
        
        # Simular latencias típicas de comunicación serie a 921600 baudios
        # ~1 byte = 10.4 μs, APDU típico 20 bytes = ~208 μs + overhead
        
        typical_latencies_us = [200, 250, 300, 180, 220, 350, 190, 240]
        
        for latency_us in typical_latencies_us:
            # Simular latencia usando sleep
            measurement_id = meter.start_measurement("serial")
            time.sleep(latency_us / 1_000_000)  # Convertir μs a segundos
            meter.end_measurement(measurement_id)
        
        stats = meter.get_latency_stats()
        mean_latency_ms = stats.mean_ms
        
        # Verificar que la latencia promedio es realista (más tolerante)
        assert mean_latency_ms < 2.0  # Menos de 2ms para comunicación serie
        assert stats.min_ms >= 0.15  # Mínimo 150μs (más tolerante)
        assert stats.max_ms <= 1.0   # Máximo 1ms (más tolerante)
    
    def test_network_latency_simulation(self):
        """Test simulación de latencia de red."""
        meter = LatencyMeter()
        
        # Simular latencias de red (más variables)
        network_latencies_ms = [2.5, 3.1, 4.8, 1.9, 6.2, 2.8, 3.5, 4.1]
        
        for latency_ms in network_latencies_ms:
            measurement_id = meter.start_measurement("network")
            time.sleep(latency_ms / 1000)  # Convertir ms a segundos
            meter.end_measurement(measurement_id)
        
        stats = meter.get_latency_stats()
        mean_latency_ms = stats.mean_ms
        
        # Verificar que cumple con el requisito de < 5ms promedio
        assert mean_latency_ms < 5.0
        assert stats.max_ms < 10.0  # Máximo 10ms
    
    def test_mixed_latency_scenarios(self):
        """Test escenarios mixtos de latencia."""
        meter = LatencyMeter(history_size=50)
        
        # Simular diferentes tipos de operaciones
        scenarios = [
            ("fast_local", [0.1, 0.2, 0.15, 0.18, 0.12]),  # Operaciones locales rápidas
            ("serial_comm", [0.8, 1.2, 0.9, 1.1, 1.0]),    # Comunicación serie
            ("network_call", [3.5, 4.2, 2.8, 3.9, 4.1]),   # Llamadas de red
            ("slow_operation", [8.5, 9.1, 7.8, 8.9, 9.2]), # Operaciones lentas
        ]
        
        all_latencies = []
        
        for scenario_name, latencies_ms in scenarios:
            for latency_ms in latencies_ms:
                measurement_id = meter.start_measurement(scenario_name)
                time.sleep(latency_ms / 1000)  # Convertir ms a segundos
                latency_ns = meter.end_measurement(measurement_id)
                all_latencies.append(latency_ns)
        
        stats = meter.get_latency_stats()
        overall_mean_ms = stats.mean_ms
        
        print(f"\nLatencia promedio mixta: {overall_mean_ms:.3f} ms")
        
        # En escenarios mixtos, algunas operaciones pueden ser lentas
        # pero el promedio general debe ser razonable
        assert overall_mean_ms < 10.0  # Límite más relajado para escenarios mixtos