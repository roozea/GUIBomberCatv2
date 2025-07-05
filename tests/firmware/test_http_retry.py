"""Tests para el cliente HTTP con retry automático."""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import httpx

from modules.bombercat_flash.http_client import (
    HttpClient,
    HttpClientError,
    RateLimitError
)


class TestHttpClient:
    """Tests para la clase HttpClient."""
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test que el cliente funciona como context manager."""
        async with HttpClient() as client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)
        
        # Después del context manager, el cliente debe estar cerrado
        assert client._client is None
    
    @pytest.mark.asyncio
    async def test_get_success(self):
        """Test petición GET exitosa."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                response = await client.get("https://api.example.com/test")
                
                assert response == mock_response
                mock_client.get.assert_called_once_with("https://api.example.com/test")
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_error(self):
        """Test manejo de rate limit (403)."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Rate limit exceeded"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                with pytest.raises(RateLimitError, match="Rate limit alcanzado"):
                    await client.get("https://api.example.com/test")
    
    @pytest.mark.asyncio
    async def test_get_http_error(self):
        """Test manejo de errores HTTP."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Not found"
            
            http_error = httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=mock_response
            )
            mock_client.get.side_effect = http_error
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                with pytest.raises(HttpClientError, match="Error HTTP 404"):
                    await client.get("https://api.example.com/test")
    
    @pytest.mark.asyncio
    async def test_get_connection_error(self):
        """Test manejo de errores de conexión."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                with pytest.raises(HttpClientError, match="Error de conexión"):
                    await client.get("https://api.example.com/test")
    
    @pytest.mark.asyncio
    async def test_get_without_context_manager(self):
        """Test que falla si no se usa como context manager."""
        client = HttpClient()
        
        with pytest.raises(HttpClientError, match="Cliente no inicializado"):
            await client.get("https://api.example.com/test")
    
    @pytest.mark.asyncio
    async def test_stream_success(self):
        """Test streaming exitoso."""
        test_data = [b"chunk1", b"chunk2", b"chunk3"]
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes.return_value = iter(test_data)
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.stream.return_value.__aenter__.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                chunks = []
                async for chunk in client.stream("https://api.example.com/file"):
                    chunks.append(chunk)
                
                assert chunks == test_data
    
    @pytest.mark.asyncio
    async def test_stream_rate_limit_error(self):
        """Test manejo de rate limit en streaming."""
        mock_response = AsyncMock()
        mock_response.status_code = 403
        mock_response.aread.return_value = b"Rate limit exceeded"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.stream.return_value.__aenter__.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                with pytest.raises(RateLimitError, match="Rate limit alcanzado"):
                    async for chunk in client.stream("https://api.example.com/file"):
                        pass
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test que el mecanismo de retry funciona."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            
            # Primera llamada falla, segunda funciona
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {"success": True}
            
            mock_client.get.side_effect = [
                httpx.ConnectError("Connection failed"),
                mock_response_success
            ]
            mock_client_class.return_value = mock_client
            
            async with HttpClient() as client:
                response = await client.get("https://api.example.com/test")
                
                assert response == mock_response_success
                assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_timeout_configuration(self):
        """Test configuración de timeout."""
        timeout = 60.0
        
        with patch('httpx.AsyncClient') as mock_client_class:
            async with HttpClient(timeout=timeout) as client:
                pass
            
            # Verificar que se pasó el timeout correcto
            call_args = mock_client_class.call_args
            assert call_args[1]['timeout'].timeout == timeout
    
    @pytest.mark.asyncio
    async def test_http2_enabled(self):
        """Test que HTTP/2 está habilitado."""
        with patch('httpx.AsyncClient') as mock_client_class:
            async with HttpClient() as client:
                pass
            
            # Verificar que HTTP/2 está habilitado
            call_args = mock_client_class.call_args
            assert call_args[1]['http2'] is True