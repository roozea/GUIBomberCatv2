"""Cliente HTTP con retry automático para descargas de firmware.

Este módulo proporciona un wrapper sobre httpx con capacidades de retry
automático usando tenacity para manejar fallos de red temporales.
"""

import logging
from typing import Optional, AsyncGenerator
from pathlib import Path

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)


logger = logging.getLogger(__name__)


class HttpClientError(Exception):
    """Error base para el cliente HTTP."""
    pass


class RateLimitError(HttpClientError):
    """Error cuando se alcanza el límite de rate de la API."""
    pass


class HttpClient:
    """Cliente HTTP asíncrono con retry automático."""
    
    def __init__(self, timeout: float = 30.0):
        """Inicializa el cliente HTTP.
        
        Args:
            timeout: Timeout en segundos para las requests.
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Entrada del context manager."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            http2=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Salida del context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Realiza una petición GET con retry automático.
        
        Args:
            url: URL a solicitar.
            **kwargs: Argumentos adicionales para httpx.
            
        Returns:
            Respuesta HTTP.
            
        Raises:
            RateLimitError: Si se alcanza el límite de rate (403).
            HttpClientError: Para otros errores HTTP.
        """
        if not self._client:
            raise HttpClientError("Cliente no inicializado. Usar como context manager.")
        
        try:
            response = await self._client.get(url, **kwargs)
            
            # Manejar rate limit específicamente
            if response.status_code == 403:
                logger.warning(f"Rate limit alcanzado para {url}")
                raise RateLimitError(f"Rate limit alcanzado: {response.text}")
            
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP {e.response.status_code} para {url}: {e.response.text}")
            raise HttpClientError(f"Error HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Error de conexión para {url}: {e}")
            raise HttpClientError(f"Error de conexión: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def stream(self, url: str, **kwargs) -> AsyncGenerator[bytes, None]:
        """Realiza una petición GET con streaming y retry automático.
        
        Args:
            url: URL a solicitar.
            **kwargs: Argumentos adicionales para httpx.
            
        Yields:
            Chunks de bytes del contenido.
            
        Raises:
            RateLimitError: Si se alcanza el límite de rate (403).
            HttpClientError: Para otros errores HTTP.
        """
        if not self._client:
            raise HttpClientError("Cliente no inicializado. Usar como context manager.")
        
        try:
            async with self._client.stream('GET', url, **kwargs) as response:
                # Manejar rate limit específicamente
                if response.status_code == 403:
                    logger.warning(f"Rate limit alcanzado para {url}")
                    raise RateLimitError(f"Rate limit alcanzado: {await response.aread()}")
                
                response.raise_for_status()
                
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP {e.response.status_code} para {url}")
            raise HttpClientError(f"Error HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Error de conexión para {url}: {e}")
            raise HttpClientError(f"Error de conexión: {e}")