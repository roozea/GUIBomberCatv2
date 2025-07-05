"""Gestor de firmware para BomberCat.

Este módulo maneja la descarga, verificación y gestión de firmware
desde el repositorio bombercat/firmware-releases en GitHub.
"""

import asyncio
import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from tqdm.asyncio import tqdm
except ImportError:
    tqdm = None

from modules.bombercat_flash.http_client import HttpClient, RateLimitError, HttpClientError


logger = logging.getLogger(__name__)


class FirmwareError(Exception):
    """Error base para operaciones de firmware."""
    pass


class ChecksumError(FirmwareError):
    """Error cuando el checksum del firmware no coincide."""
    pass


class AssetNotFoundError(FirmwareError):
    """Error cuando no se encuentra el asset de firmware."""
    pass


class FirmwareManager:
    """Gestor de firmware para dispositivos BomberCat."""
    
    def __init__(self, repo: str = "bombercat/firmware-releases"):
        """Inicializa el gestor de firmware.
        
        Args:
            repo: Repositorio de GitHub en formato 'owner/repo'.
        """
        self.repo = repo
        self.github_api_base = "https://api.github.com"
        
    async def get_latest_release(self) -> Dict[str, Any]:
        """Obtiene información del último release desde GitHub.
        
        Returns:
            Diccionario con información del release.
            
        Raises:
            FirmwareError: Si no se puede obtener el release.
        """
        url = f"{self.github_api_base}/repos/{self.repo}/releases/latest"
        
        async with HttpClient(timeout=30.0) as client:
            try:
                response = await client.get(url)
                release_data = response.json()
                
                logger.info(f"Obtenido release {release_data.get('tag_name', 'unknown')}")
                return release_data
                
            except RateLimitError:
                logger.warning("Rate limit alcanzado, esperando 60 segundos...")
                await asyncio.sleep(60)
                # Reintentar una vez más
                response = await client.get(url)
                return response.json()
                
            except HttpClientError as e:
                raise FirmwareError(f"Error obteniendo release: {e}")
    
    def _find_firmware_asset(self, release_json: Dict[str, Any]) -> Dict[str, str]:
        """Encuentra el asset de firmware correcto en el release.
        
        Args:
            release_json: JSON del release de GitHub.
            
        Returns:
            Diccionario con name, sha256 y download_url del asset.
            
        Raises:
            AssetNotFoundError: Si no se encuentra un asset válido.
        """
        assets = release_json.get('assets', [])
        
        for asset in assets:
            name = asset.get('name', '')
            
            # Filtrar por extensión .bin y arquitectura esp32s2
            if name.endswith('.bin') and 'esp32s2' in name.lower():
                # Buscar el checksum en el body del release
                body = release_json.get('body', '')
                sha256 = self._extract_sha256_from_body(body, name)
                
                if sha256:
                    logger.info(f"Asset encontrado: {name}")
                    return {
                        'name': name,
                        'sha256': sha256,
                        'download_url': asset['browser_download_url']
                    }
        
        raise AssetNotFoundError(
            f"No se encontró asset de firmware ESP32-S2 en release {release_json.get('tag_name', 'unknown')}"
        )
    
    def _extract_sha256_from_body(self, body: str, filename: str) -> Optional[str]:
        """Extrae el SHA256 del cuerpo del release para un archivo específico.
        
        Args:
            body: Cuerpo del release.
            filename: Nombre del archivo.
            
        Returns:
            SHA256 si se encuentra, None en caso contrario.
        """
        lines = body.split('\n')
        
        for line in lines:
            line = line.strip()
            # Buscar líneas que contengan el filename y un hash
            if filename in line and len(line.split()) >= 2:
                parts = line.split()
                for part in parts:
                    # SHA256 tiene 64 caracteres hexadecimales
                    if len(part) == 64 and all(c in '0123456789abcdefABCDEF' for c in part):
                        return part.lower()
        
        return None
    
    async def download_firmware(
        self, 
        version: Optional[str] = None, 
        target_path: Optional[Path] = None
    ) -> Path:
        """Descarga firmware de forma asíncrona con progreso.
        
        Args:
            version: Versión específica (None para la última).
            target_path: Ruta de destino (None para generar automáticamente).
            
        Returns:
            Ruta del archivo descargado.
            
        Raises:
            FirmwareError: Si hay error en la descarga.
            ChecksumError: Si el checksum no coincide.
        """
        # Obtener información del release
        if version:
            # TODO: Implementar descarga de versión específica
            raise NotImplementedError("Descarga de versión específica no implementada")
        else:
            release_data = await self.get_latest_release()
        
        # Encontrar el asset correcto
        asset_info = self._find_firmware_asset(release_data)
        
        # Determinar ruta de destino
        if target_path is None:
            target_path = Path.cwd() / "firmware" / asset_info['name']
        
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Descargar con progreso
        await self._download_with_progress(
            asset_info['download_url'],
            target_path,
            asset_info['name']
        )
        
        # Verificar checksum
        if not self._verify_checksum(target_path, asset_info['sha256']):
            target_path.unlink(missing_ok=True)
            raise ChecksumError(
                f"Checksum no coincide para {asset_info['name']}. "
                f"Esperado: {asset_info['sha256']}"
            )
        
        logger.info(f"Firmware descargado y verificado: {target_path}")
        return target_path
    
    async def _download_with_progress(
        self, 
        url: str, 
        target_path: Path, 
        filename: str
    ) -> None:
        """Descarga un archivo con barra de progreso.
        
        Args:
            url: URL de descarga.
            target_path: Ruta de destino.
            filename: Nombre del archivo para mostrar.
        """
        async with HttpClient(timeout=60.0) as client:
            # Obtener tamaño del archivo
            head_response = await client.get(url, headers={'Range': 'bytes=0-0'})
            total_size = None
            
            if 'content-range' in head_response.headers:
                total_size = int(head_response.headers['content-range'].split('/')[-1])
            elif 'content-length' in head_response.headers:
                total_size = int(head_response.headers['content-length'])
            
            # Configurar barra de progreso
            progress_bar = None
            if tqdm and sys.stderr.isatty() and total_size:
                progress_bar = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    desc=f"Descargando {filename}"
                )
            
            try:
                with open(target_path, 'wb') as f:
                    async for chunk in client.stream(url):
                        f.write(chunk)
                        if progress_bar:
                            progress_bar.update(len(chunk))
                            
            finally:
                if progress_bar:
                    progress_bar.close()
    
    def _verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verifica el checksum SHA256 de un archivo.
        
        Args:
            file_path: Ruta del archivo a verificar.
            expected_sha256: SHA256 esperado en hexadecimal.
            
        Returns:
            True si el checksum coincide, False en caso contrario.
        """
        if not file_path.exists():
            return False
        
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Leer en chunks para archivos grandes
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256_hash.update(chunk)
            
            calculated_hash = sha256_hash.hexdigest().lower()
            expected_hash = expected_sha256.lower()
            
            logger.debug(f"Checksum calculado: {calculated_hash}")
            logger.debug(f"Checksum esperado: {expected_hash}")
            
            return calculated_hash == expected_hash
            
        except Exception as e:
            logger.error(f"Error verificando checksum: {e}")
            return False
    
    async def list_available_versions(self) -> list[str]:
        """Lista las versiones de firmware disponibles.
        
        Returns:
            Lista de versiones disponibles.
        """
        url = f"{self.github_api_base}/repos/{self.repo}/releases"
        
        async with HttpClient() as client:
            try:
                response = await client.get(url)
                releases = response.json()
                
                versions = []
                for release in releases:
                    if not release.get('draft', False) and not release.get('prerelease', False):
                        versions.append(release['tag_name'])
                
                return versions
                
            except HttpClientError as e:
                raise FirmwareError(f"Error obteniendo versiones: {e}")