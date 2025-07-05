"""NFC Relay Core Coordinator

Coordinador principal que unifica pipelines bidireccionales client↔host.
Maneja tasks asyncio, control de flujo y monitoreo de métricas.
"""

import asyncio
import threading
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from modules.bombercat_relay.serial_pipeline import SerialPipeline, SerialConfig, PipelineState
from modules.bombercat_relay.ring_buffer import RingBuffer
from modules.bombercat_relay.apdu import APDU, is_complete, parse_apdu, validate_apdu_structure
from modules.bombercat_relay.metrics import LatencyMeter, MetricsCollector, MetricSnapshot


class RelayState(Enum):
    """Estados del relay NFC."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class RelayError(Exception):
    """Excepción específica del relay NFC."""
    pass


@dataclass
class RelayConfig:
    """Configuración del relay NFC."""
    client_port: str
    host_port: str
    baudrate: int = 921600
    buffer_size: int = 8192
    latency_threshold_ms: float = 5.0
    enable_flow_control: bool = True
    enable_apdu_validation: bool = True
    retry_attempts: int = 1
    
    def get_client_config(self) -> SerialConfig:
        """Obtiene configuración para puerto cliente."""
        return SerialConfig(
            port=self.client_port,
            baudrate=self.baudrate,
            timeout=0.001,
            write_timeout=0.001
        )
    
    def get_host_config(self) -> SerialConfig:
        """Obtiene configuración para puerto host."""
        return SerialConfig(
            port=self.host_port,
            baudrate=self.baudrate,
            timeout=0.001,
            write_timeout=0.001
        )


@dataclass
class RelayStats:
    """Estadísticas del relay."""
    client_to_host_bytes: int = 0
    host_to_client_bytes: int = 0
    client_to_host_apdus: int = 0
    host_to_client_apdus: int = 0
    validation_errors: int = 0
    flow_control_events: int = 0
    retries: int = 0
    uptime_seconds: float = 0.0


class NFCRelayService:
    """Servicio de relay NFC bidireccional.
    
    Coordina el relay de datos APDU entre cliente y host con:
    - Latencia < 5ms
    - Validación APDU
    - Control de flujo
    - Monitoreo en tiempo real
    - Manejo de errores
    """
    
    def __init__(self, config: RelayConfig):
        """Inicializa el servicio de relay.
        
        Args:
            config: Configuración del relay
        """
        self.config = config
        
        # Estado del relay
        self._state = RelayState.STOPPED
        self._state_lock = threading.RLock()
        self._start_time = 0.0
        
        # Pipelines serie
        self.client_pipeline: Optional[SerialPipeline] = None
        self.host_pipeline: Optional[SerialPipeline] = None
        
        # Buffers intermedios para APDU completos
        self._client_buffer = bytearray()
        self._host_buffer = bytearray()
        
        # Métricas
        self.metrics_collector = MetricsCollector()
        self.client_to_host_meter = LatencyMeter(history_size=100)
        self.host_to_client_meter = LatencyMeter(history_size=100)
        
        # Configurar thresholds
        self.client_to_host_meter.set_latency_threshold(config.latency_threshold_ms)
        self.host_to_client_meter.set_latency_threshold(config.latency_threshold_ms)
        
        # Agregar meters al collector
        self.metrics_collector.add_meter("client_to_host", self.client_to_host_meter)
        self.metrics_collector.add_meter("host_to_client", self.host_to_client_meter)
        
        # Tasks asyncio
        self._relay_tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        
        # Estadísticas
        self.stats = RelayStats()
        
        # Callbacks
        self.on_apdu_relayed: Optional[Callable[[str, APDU], None]] = None
        self.on_validation_error: Optional[Callable[[str, bytes, str], None]] = None
        self.on_flow_control: Optional[Callable[[str, str], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    @property
    def state(self) -> RelayState:
        """Estado actual del relay."""
        with self._state_lock:
            return self._state
    
    @property
    def is_running(self) -> bool:
        """True si el relay está ejecutándose."""
        return self.state == RelayState.RUNNING
    
    @property
    def uptime(self) -> float:
        """Tiempo de funcionamiento en segundos."""
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time
    
    async def start(self) -> bool:
        """Inicia el servicio de relay.
        
        Returns:
            True si se inició correctamente
        """
        with self._state_lock:
            if self._state != RelayState.STOPPED:
                return False
            
            self._state = RelayState.STARTING
        
        try:
            # Crear pipelines
            await self._create_pipelines()
            
            # Iniciar pipelines
            if not self._start_pipelines():
                raise RelayError("No se pudieron iniciar los pipelines")
            
            # Configurar callbacks
            self._setup_pipeline_callbacks()
            
            # Iniciar tasks asyncio
            await self._start_relay_tasks()
            
            # Marcar como iniciado
            self._start_time = time.time()
            
            with self._state_lock:
                self._state = RelayState.RUNNING
            
            return True
            
        except Exception as e:
            with self._state_lock:
                self._state = RelayState.ERROR
            
            if self.on_error:
                self.on_error(e)
            
            await self._cleanup()
            return False
    
    async def stop(self) -> None:
        """Detiene el servicio de relay."""
        with self._state_lock:
            if self._state in [RelayState.STOPPED, RelayState.STOPPING]:
                return
            
            self._state = RelayState.STOPPING
        
        # Señalar parada
        self._stop_event.set()
        
        # Cancelar tasks
        await self._cancel_relay_tasks()
        
        # Limpiar recursos
        await self._cleanup()
        
        with self._state_lock:
            self._state = RelayState.STOPPED
    
    def get_metrics(self) -> Dict[str, MetricSnapshot]:
        """Obtiene métricas actuales del relay.
        
        Returns:
            Diccionario con snapshots de métricas
        """
        snapshots = self.metrics_collector.get_all_snapshots()
        
        # Agregar uso de buffers
        if self.client_pipeline and self.host_pipeline:
            for name, snapshot in snapshots.items():
                if name == "client_to_host":
                    snapshot.buffer_usage = {
                        'rx_buffer': self.client_pipeline.rx_buffer.size / self.client_pipeline.rx_buffer.capacity,
                        'tx_buffer': self.host_pipeline.tx_buffer.size / self.host_pipeline.tx_buffer.capacity
                    }
                elif name == "host_to_client":
                    snapshot.buffer_usage = {
                        'rx_buffer': self.host_pipeline.rx_buffer.size / self.host_pipeline.rx_buffer.capacity,
                        'tx_buffer': self.client_pipeline.tx_buffer.size / self.client_pipeline.tx_buffer.capacity
                    }
        
        return snapshots
    
    def get_stats(self) -> RelayStats:
        """Obtiene estadísticas del relay.
        
        Returns:
            Estadísticas actuales
        """
        self.stats.uptime_seconds = self.uptime
        return self.stats
    
    async def _create_pipelines(self) -> None:
        """Crea los pipelines serie."""
        # Crear buffers
        client_rx_buffer = RingBuffer(self.config.buffer_size)
        client_tx_buffer = RingBuffer(self.config.buffer_size)
        host_rx_buffer = RingBuffer(self.config.buffer_size)
        host_tx_buffer = RingBuffer(self.config.buffer_size)
        
        # Crear pipelines
        self.client_pipeline = SerialPipeline(
            rx_config=self.config.get_client_config(),
            tx_config=self.config.get_client_config(),
            rx_buffer=client_rx_buffer,
            tx_buffer=client_tx_buffer
        )
        
        self.host_pipeline = SerialPipeline(
            rx_config=self.config.get_host_config(),
            tx_config=self.config.get_host_config(),
            rx_buffer=host_rx_buffer,
            tx_buffer=host_tx_buffer
        )
    
    def _start_pipelines(self) -> bool:
        """Inicia los pipelines serie.
        
        Returns:
            True si ambos se iniciaron correctamente
        """
        if not self.client_pipeline or not self.host_pipeline:
            return False
        
        client_started = self.client_pipeline.start()
        host_started = self.host_pipeline.start()
        
        return client_started and host_started
    
    def _setup_pipeline_callbacks(self) -> None:
        """Configura callbacks de los pipelines."""
        if self.client_pipeline:
            self.client_pipeline.on_error = self._handle_pipeline_error
        
        if self.host_pipeline:
            self.host_pipeline.on_error = self._handle_pipeline_error
    
    async def _start_relay_tasks(self) -> None:
        """Inicia las tasks de relay."""
        self._stop_event.clear()
        
        # Task para relay client → host
        client_to_host_task = asyncio.create_task(
            self._relay_client_to_host(),
            name="relay-client-to-host"
        )
        
        # Task para relay host → client
        host_to_client_task = asyncio.create_task(
            self._relay_host_to_client(),
            name="relay-host-to-client"
        )
        
        self._relay_tasks = [client_to_host_task, host_to_client_task]
    
    async def _relay_client_to_host(self) -> None:
        """Task para relay de datos client → host."""
        while not self._stop_event.is_set():
            try:
                await self._process_direction(
                    source=self.client_pipeline,
                    target=self.host_pipeline,
                    buffer=self._client_buffer,
                    direction="client_to_host",
                    meter=self.client_to_host_meter
                )
                
                # Pequeña pausa para evitar busy waiting
                await asyncio.sleep(0.0001)  # 0.1ms
                
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                break
    
    async def _relay_host_to_client(self) -> None:
        """Task para relay de datos host → client."""
        while not self._stop_event.is_set():
            try:
                await self._process_direction(
                    source=self.host_pipeline,
                    target=self.client_pipeline,
                    buffer=self._host_buffer,
                    direction="host_to_client",
                    meter=self.host_to_client_meter
                )
                
                # Pequeña pausa para evitar busy waiting
                await asyncio.sleep(0.0001)  # 0.1ms
                
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                break
    
    async def _process_direction(self, 
                               source: SerialPipeline,
                               target: SerialPipeline,
                               buffer: bytearray,
                               direction: str,
                               meter: LatencyMeter) -> None:
        """Procesa datos en una dirección.
        
        Args:
            source: Pipeline fuente
            target: Pipeline destino
            buffer: Buffer intermedio
            direction: Dirección del relay
            meter: Medidor de latencia
        """
        # Leer datos del source
        data = source.read(1024)
        if not data:
            return
        
        # Agregar a buffer intermedio
        buffer.extend(data)
        
        # Procesar APDUs completos
        while buffer:
            if not is_complete(buffer):
                break
            
            # Parsear APDU
            apdu = parse_apdu(buffer, validate=self.config.enable_apdu_validation)
            if not apdu:
                # APDU inválido - descartar primer byte y continuar
                buffer.pop(0)
                self.stats.validation_errors += 1
                
                if self.on_validation_error:
                    self.on_validation_error(direction, bytes(buffer[:10]), "APDU inválido")
                continue
            
            # Remover APDU del buffer
            apdu_length = apdu.expected_length
            apdu_data = bytes(buffer[:apdu_length])
            del buffer[:apdu_length]
            
            # Medir latencia y enviar
            measurement_id = meter.start_measurement()
            
            try:
                # Enviar con retry si está habilitado
                success = await self._send_with_retry(target, apdu_data, direction)
                
                if success:
                    # Finalizar medición
                    latency_ns = meter.end_measurement(measurement_id)
                    
                    # Actualizar estadísticas
                    if direction == "client_to_host":
                        self.stats.client_to_host_bytes += len(apdu_data)
                        self.stats.client_to_host_apdus += 1
                    else:
                        self.stats.host_to_client_bytes += len(apdu_data)
                        self.stats.host_to_client_apdus += 1
                    
                    # Callback
                    if self.on_apdu_relayed:
                        self.on_apdu_relayed(direction, apdu)
                    
                    # Registrar throughput
                    meter.record_throughput(len(apdu_data), 1)
                    
                else:
                    # Error en envío
                    meter.record_error()
                    meter.end_measurement(measurement_id)
                    
            except Exception as e:
                meter.record_error()
                meter.end_measurement(measurement_id)
                raise e
    
    async def _send_with_retry(self, 
                             target: SerialPipeline, 
                             data: bytes, 
                             direction: str) -> bool:
        """Envía datos con retry.
        
        Args:
            target: Pipeline destino
            data: Datos a enviar
            direction: Dirección del envío
            
        Returns:
            True si se envió correctamente
        """
        for attempt in range(self.config.retry_attempts + 1):
            try:
                bytes_written = target.write(data)
                
                if bytes_written == len(data):
                    return True
                
                # Envío parcial - reintentar
                if attempt < self.config.retry_attempts:
                    self.stats.retries += 1
                    await asyncio.sleep(0.001)  # 1ms delay
                    continue
                
                return False
                
            except Exception:
                if attempt < self.config.retry_attempts:
                    self.stats.retries += 1
                    await asyncio.sleep(0.001)
                    continue
                
                return False
        
        return False
    
    def _handle_pipeline_error(self, error: Exception) -> None:
        """Maneja errores de pipeline.
        
        Args:
            error: Error ocurrido
        """
        if self.on_error:
            self.on_error(error)
    
    async def _cancel_relay_tasks(self) -> None:
        """Cancela las tasks de relay."""
        for task in self._relay_tasks:
            if not task.done():
                task.cancel()
        
        # Esperar cancelación
        if self._relay_tasks:
            await asyncio.gather(*self._relay_tasks, return_exceptions=True)
        
        self._relay_tasks.clear()
    
    async def _cleanup(self) -> None:
        """Limpia recursos."""
        # Detener pipelines
        if self.client_pipeline:
            self.client_pipeline.stop()
        
        if self.host_pipeline:
            self.host_pipeline.stop()
        
        # Limpiar buffers
        self._client_buffer.clear()
        self._host_buffer.clear()
        
        # Reset métricas si es necesario
        # self.metrics_collector.reset_all()