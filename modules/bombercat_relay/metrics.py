"""Monitor de Latencia de Alta Resolución para NFC Relay

Implementa medición de latencia en tiempo real con precisión de nanosegundos.
Mantiene estadísticas históricas y métricas de rendimiento.
"""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from statistics import mean, median, stdev
from enum import Enum


class MetricType(Enum):
    """Tipos de métricas disponibles."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    BUFFER_USAGE = "buffer_usage"


@dataclass
class LatencyStats:
    """Estadísticas de latencia."""
    count: int = 0
    min_ns: int = 0
    max_ns: int = 0
    mean_ns: float = 0.0
    median_ns: float = 0.0
    std_dev_ns: float = 0.0
    p95_ns: float = 0.0
    p99_ns: float = 0.0
    
    @property
    def min_ms(self) -> float:
        """Latencia mínima en milisegundos."""
        return self.min_ns / 1_000_000
    
    @property
    def max_ms(self) -> float:
        """Latencia máxima en milisegundos."""
        return self.max_ns / 1_000_000
    
    @property
    def mean_ms(self) -> float:
        """Latencia promedio en milisegundos."""
        return self.mean_ns / 1_000_000
    
    @property
    def median_ms(self) -> float:
        """Latencia mediana en milisegundos."""
        return self.median_ns / 1_000_000
    
    @property
    def std_dev_ms(self) -> float:
        """Desviación estándar en milisegundos."""
        return self.std_dev_ns / 1_000_000
    
    @property
    def p95_ms(self) -> float:
        """Percentil 95 en milisegundos."""
        return self.p95_ns / 1_000_000
    
    @property
    def p99_ms(self) -> float:
        """Percentil 99 en milisegundos."""
        return self.p99_ns / 1_000_000


@dataclass
class ThroughputStats:
    """Estadísticas de throughput."""
    bytes_per_second: float = 0.0
    messages_per_second: float = 0.0
    total_bytes: int = 0
    total_messages: int = 0
    duration_seconds: float = 0.0


@dataclass
class MetricSnapshot:
    """Snapshot de métricas en un momento dado."""
    timestamp: float
    latency: LatencyStats
    throughput: ThroughputStats
    error_rate: float = 0.0
    buffer_usage: Dict[str, float] = field(default_factory=dict)


class LatencyMeter:
    """Monitor de latencia de alta resolución.
    
    Mide latencias con precisión de nanosegundos y mantiene
    estadísticas históricas para análisis de rendimiento.
    """
    
    def __init__(self, 
                 history_size: int = 100,
                 enable_async_publishing: bool = True):
        """Inicializa el monitor de latencia.
        
        Args:
            history_size: Número de latencias a mantener en historial
            enable_async_publishing: Si habilitar publicación async de métricas
        """
        self.history_size = history_size
        self.enable_async_publishing = enable_async_publishing
        
        # Historial de latencias (en nanosegundos)
        self._latencies = deque(maxlen=history_size)
        self._lock = threading.RLock()
        
        # Timestamps activos para medición
        self._active_measurements: Dict[str, int] = {}
        
        # Estadísticas de throughput
        self._start_time = time.perf_counter()
        self._total_bytes = 0
        self._total_messages = 0
        self._error_count = 0
        
        # Cola async para publicar métricas
        self._metric_queue: Optional[asyncio.Queue] = None
        if enable_async_publishing:
            try:
                self._metric_queue = asyncio.Queue(maxsize=1000)
            except RuntimeError:
                # No hay loop asyncio activo
                self._metric_queue = None
        
        # Callbacks
        self.on_latency_measured: Optional[Callable[[int], None]] = None
        self.on_threshold_exceeded: Optional[Callable[[int, int], None]] = None
        
        # Configuración de alertas
        self.latency_threshold_ns = 5_000_000  # 5ms por defecto
    
    def start_measurement(self, measurement_id: str = "default") -> str:
        """Inicia una medición de latencia.
        
        Args:
            measurement_id: ID único para la medición
            
        Returns:
            ID de la medición iniciada
        """
        timestamp = time.perf_counter_ns()
        
        with self._lock:
            self._active_measurements[measurement_id] = timestamp
        
        return measurement_id
    
    def end_measurement(self, measurement_id: str = "default") -> Optional[int]:
        """Finaliza una medición de latencia.
        
        Args:
            measurement_id: ID de la medición a finalizar
            
        Returns:
            Latencia en nanosegundos o None si no se encontró la medición
        """
        end_time = time.perf_counter_ns()
        
        with self._lock:
            start_time = self._active_measurements.pop(measurement_id, None)
            
            if start_time is None:
                return None
            
            latency_ns = end_time - start_time
            self._latencies.append(latency_ns)
            
            # Callback
            if self.on_latency_measured:
                self.on_latency_measured(latency_ns)
            
            # Verificar threshold
            if latency_ns > self.latency_threshold_ns and self.on_threshold_exceeded:
                self.on_threshold_exceeded(latency_ns, self.latency_threshold_ns)
            
            # Publicar métrica async
            if self._metric_queue:
                try:
                    self._metric_queue.put_nowait({
                        'type': MetricType.LATENCY,
                        'value': latency_ns,
                        'timestamp': end_time
                    })
                except asyncio.QueueFull:
                    pass  # Descartar si la cola está llena
            
            return latency_ns
    
    def measure_latency(self, func: Callable, *args, **kwargs) -> tuple[Any, int]:
        """Mide la latencia de una función.
        
        Args:
            func: Función a medir
            *args: Argumentos posicionales
            **kwargs: Argumentos nombrados
            
        Returns:
            Tupla (resultado_función, latencia_ns)
        """
        start_time = time.perf_counter_ns()
        result = func(*args, **kwargs)
        end_time = time.perf_counter_ns()
        
        latency_ns = end_time - start_time
        
        with self._lock:
            self._latencies.append(latency_ns)
        
        return result, latency_ns
    
    async def measure_latency_async(self, coro) -> tuple[Any, int]:
        """Mide la latencia de una corrutina.
        
        Args:
            coro: Corrutina a medir
            
        Returns:
            Tupla (resultado, latencia_ns)
        """
        start_time = time.perf_counter_ns()
        result = await coro
        end_time = time.perf_counter_ns()
        
        latency_ns = end_time - start_time
        
        with self._lock:
            self._latencies.append(latency_ns)
        
        return result, latency_ns
    
    def record_throughput(self, bytes_processed: int, message_count: int = 1) -> None:
        """Registra datos de throughput.
        
        Args:
            bytes_processed: Bytes procesados
            message_count: Número de mensajes procesados
        """
        with self._lock:
            self._total_bytes += bytes_processed
            self._total_messages += message_count
    
    def record_error(self) -> None:
        """Registra un error."""
        with self._lock:
            self._error_count += 1
    
    def get_latency_stats(self) -> LatencyStats:
        """Obtiene estadísticas de latencia actuales.
        
        Returns:
            Estadísticas de latencia
        """
        with self._lock:
            if not self._latencies:
                return LatencyStats()
            
            latencies = list(self._latencies)
        
        # Calcular estadísticas
        count = len(latencies)
        min_ns = min(latencies)
        max_ns = max(latencies)
        mean_ns = mean(latencies)
        median_ns = median(latencies)
        
        std_dev_ns = 0.0
        if count > 1:
            std_dev_ns = stdev(latencies)
        
        # Percentiles
        sorted_latencies = sorted(latencies)
        p95_idx = int(0.95 * count)
        p99_idx = int(0.99 * count)
        
        p95_ns = sorted_latencies[min(p95_idx, count - 1)]
        p99_ns = sorted_latencies[min(p99_idx, count - 1)]
        
        return LatencyStats(
            count=count,
            min_ns=min_ns,
            max_ns=max_ns,
            mean_ns=mean_ns,
            median_ns=median_ns,
            std_dev_ns=std_dev_ns,
            p95_ns=p95_ns,
            p99_ns=p99_ns
        )
    
    def get_throughput_stats(self) -> ThroughputStats:
        """Obtiene estadísticas de throughput.
        
        Returns:
            Estadísticas de throughput
        """
        with self._lock:
            duration = time.perf_counter() - self._start_time
            
            if duration <= 0:
                return ThroughputStats()
            
            bytes_per_second = self._total_bytes / duration
            messages_per_second = self._total_messages / duration
            
            return ThroughputStats(
                bytes_per_second=bytes_per_second,
                messages_per_second=messages_per_second,
                total_bytes=self._total_bytes,
                total_messages=self._total_messages,
                duration_seconds=duration
            )
    
    def get_error_rate(self) -> float:
        """Obtiene la tasa de error.
        
        Returns:
            Tasa de error (0.0 - 1.0)
        """
        with self._lock:
            if self._total_messages == 0:
                return 0.0
            return self._error_count / self._total_messages
    
    def get_snapshot(self, buffer_usage: Optional[Dict[str, float]] = None) -> MetricSnapshot:
        """Obtiene un snapshot completo de métricas.
        
        Args:
            buffer_usage: Uso de buffers opcional
            
        Returns:
            Snapshot de métricas
        """
        return MetricSnapshot(
            timestamp=time.time(),
            latency=self.get_latency_stats(),
            throughput=self.get_throughput_stats(),
            error_rate=self.get_error_rate(),
            buffer_usage=buffer_usage or {}
        )
    
    def reset(self) -> None:
        """Resetea todas las métricas."""
        with self._lock:
            self._latencies.clear()
            self._active_measurements.clear()
            self._start_time = time.perf_counter()
            self._total_bytes = 0
            self._total_messages = 0
            self._error_count = 0
    
    def set_latency_threshold(self, threshold_ms: float) -> None:
        """Establece el threshold de latencia para alertas.
        
        Args:
            threshold_ms: Threshold en milisegundos
        """
        self.latency_threshold_ns = int(threshold_ms * 1_000_000)
    
    async def get_metric_stream(self) -> Optional[asyncio.Queue]:
        """Obtiene la cola de métricas async.
        
        Returns:
            Cola de métricas o None si no está habilitada
        """
        return self._metric_queue
    
    def __enter__(self):
        """Context manager para medición automática."""
        self._context_id = f"context_{id(self)}"
        self.start_measurement(self._context_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finaliza medición del context manager."""
        self.end_measurement(self._context_id)


class MetricsCollector:
    """Recolector centralizado de métricas.
    
    Agrega múltiples LatencyMeter y proporciona vista unificada.
    """
    
    def __init__(self):
        self._meters: Dict[str, LatencyMeter] = {}
        self._lock = threading.RLock()
    
    def add_meter(self, name: str, meter: LatencyMeter) -> None:
        """Agrega un meter al recolector.
        
        Args:
            name: Nombre del meter
            meter: Instancia de LatencyMeter
        """
        with self._lock:
            self._meters[name] = meter
    
    def remove_meter(self, name: str) -> None:
        """Remueve un meter del recolector.
        
        Args:
            name: Nombre del meter a remover
        """
        with self._lock:
            self._meters.pop(name, None)
    
    def get_meter(self, name: str) -> Optional[LatencyMeter]:
        """Obtiene un meter por nombre.
        
        Args:
            name: Nombre del meter
            
        Returns:
            LatencyMeter o None si no existe
        """
        with self._lock:
            return self._meters.get(name)
    
    def get_all_snapshots(self) -> Dict[str, MetricSnapshot]:
        """Obtiene snapshots de todos los meters.
        
        Returns:
            Diccionario con snapshots por nombre
        """
        snapshots = {}
        
        with self._lock:
            for name, meter in self._meters.items():
                snapshots[name] = meter.get_snapshot()
        
        return snapshots
    
    def reset_all(self) -> None:
        """Resetea todos los meters."""
        with self._lock:
            for meter in self._meters.values():
                meter.reset()