"""Utilidades de back-off para reconexión.

Helper para implementar estrategias de reconexión con back-off exponencial.
"""

import asyncio
import logging
import random
from typing import Optional, Callable, Any


class ExponentialBackoff:
    """Implementa back-off exponencial con jitter.
    
    Características:
    - Back-off exponencial: 2^attempt segundos
    - Jitter aleatorio para evitar thundering herd
    - Límite máximo de tiempo de espera
    - Límite máximo de intentos
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True
    ):
        """Inicializa el back-off exponencial.
        
        Args:
            max_attempts: Máximo número de intentos
            base_delay: Delay base en segundos
            max_delay: Delay máximo en segundos
            jitter: Si agregar jitter aleatorio
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.logger = logging.getLogger(__name__)
        
        # Estado
        self.attempt = 0
        self.last_delay = 0.0
    
    def reset(self):
        """Reinicia el contador de intentos."""
        self.attempt = 0
        self.last_delay = 0.0
    
    def next_delay(self) -> Optional[float]:
        """Calcula el siguiente delay.
        
        Returns:
            Delay en segundos, o None si se alcanzó el máximo
        """
        if self.attempt >= self.max_attempts:
            return None
        
        # Calcular delay exponencial
        delay = self.base_delay * (2 ** self.attempt)
        
        # Aplicar límite máximo
        delay = min(delay, self.max_delay)
        
        # Agregar jitter si está habilitado
        if self.jitter:
            # Jitter del ±25%
            jitter_range = delay * 0.25
            jitter_offset = random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay + jitter_offset)
        
        self.last_delay = delay
        self.attempt += 1
        
        return delay
    
    async def wait(self) -> bool:
        """Espera el siguiente delay.
        
        Returns:
            True si debe continuar, False si se alcanzó el máximo
        """
        delay = self.next_delay()
        
        if delay is None:
            self.logger.warning(f"Máximo de intentos alcanzado: {self.max_attempts}")
            return False
        
        self.logger.info(f"Esperando {delay:.2f}s (intento {self.attempt}/{self.max_attempts})")
        await asyncio.sleep(delay)
        
        return True
    
    @property
    def should_continue(self) -> bool:
        """True si debe continuar intentando."""
        return self.attempt < self.max_attempts
    
    def __repr__(self) -> str:
        return (
            f"ExponentialBackoff("
            f"attempt={self.attempt}/{self.max_attempts}, "
            f"last_delay={self.last_delay:.2f}s"
            f")"
        )


async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
) -> Any:
    """Ejecuta una función con retry y back-off exponencial.
    
    Args:
        func: Función a ejecutar (puede ser async)
        max_attempts: Máximo número de intentos
        base_delay: Delay base en segundos
        max_delay: Delay máximo en segundos
        jitter: Si agregar jitter aleatorio
        exceptions: Tupla de excepciones a capturar
        
    Returns:
        Resultado de la función
        
    Raises:
        La última excepción si se agotan los intentos
    """
    backoff = ExponentialBackoff(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter
    )
    
    logger = logging.getLogger(__name__)
    last_exception = None
    
    while backoff.should_continue:
        try:
            # Ejecutar función
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()
            
            # Éxito - reiniciar contador
            backoff.reset()
            return result
            
        except exceptions as e:
            last_exception = e
            logger.warning(f"Intento {backoff.attempt + 1} falló: {e}")
            
            # Esperar antes del siguiente intento
            if not await backoff.wait():
                break
    
    # Se agotaron los intentos
    logger.error(f"Función falló después de {max_attempts} intentos")
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError(f"Función falló después de {max_attempts} intentos")


class ConnectionRetryManager:
    """Gestor de reintentos para conexiones.
    
    Maneja el estado de reconexión y proporciona callbacks.
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        """Inicializa el gestor de reintentos.
        
        Args:
            max_attempts: Máximo número de intentos
            base_delay: Delay base en segundos
            max_delay: Delay máximo en segundos
        """
        self.backoff = ExponentialBackoff(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay
        )
        
        self.logger = logging.getLogger(__name__)
        self._is_retrying = False
        self._retry_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self.on_retry_start: Optional[Callable] = None
        self.on_retry_attempt: Optional[Callable[[int], None]] = None
        self.on_retry_success: Optional[Callable] = None
        self.on_retry_failed: Optional[Callable] = None
    
    @property
    def is_retrying(self) -> bool:
        """True si está en proceso de retry."""
        return self._is_retrying
    
    @property
    def current_attempt(self) -> int:
        """Número del intento actual."""
        return self.backoff.attempt
    
    async def start_retry(self, connect_func: Callable) -> bool:
        """Inicia el proceso de retry.
        
        Args:
            connect_func: Función de conexión a ejecutar
            
        Returns:
            True si la conexión fue exitosa
        """
        if self._is_retrying:
            self.logger.warning("Ya hay un proceso de retry en curso")
            return False
        
        self._is_retrying = True
        self.backoff.reset()
        
        if self.on_retry_start:
            self.on_retry_start()
        
        try:
            while self.backoff.should_continue:
                if self.on_retry_attempt:
                    self.on_retry_attempt(self.backoff.attempt + 1)
                
                try:
                    # Intentar conectar
                    if asyncio.iscoroutinefunction(connect_func):
                        await connect_func()
                    else:
                        connect_func()
                    
                    # Éxito
                    self.logger.info("Reconexión exitosa")
                    if self.on_retry_success:
                        self.on_retry_success()
                    
                    return True
                    
                except Exception as e:
                    self.logger.warning(f"Intento {self.backoff.attempt + 1} falló: {e}")
                    
                    # Esperar antes del siguiente intento
                    if not await self.backoff.wait():
                        break
            
            # Se agotaron los intentos
            self.logger.error("Reconexión falló después de todos los intentos")
            if self.on_retry_failed:
                self.on_retry_failed()
            
            return False
            
        finally:
            self._is_retrying = False
    
    def stop_retry(self):
        """Detiene el proceso de retry."""
        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
        
        self._is_retrying = False
        self.backoff.reset()
    
    def __repr__(self) -> str:
        return (
            f"ConnectionRetryManager("
            f"retrying={self._is_retrying}, "
            f"attempt={self.current_attempt}"
            f")"
        )