"""ESPTool adapter for flashing ESP32/ESP8266 devices."""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any

import serial
import serial.tools.list_ports
from esptool import main as esptool_main

from adapters.interfaces.services import FlashingServiceInterface, DeviceDiscoveryServiceInterface
from core.entities.device import Device, DeviceType
from core.entities.firmware import Firmware
from core.use_cases.device_flashing import FlashingProgress, FlashingStatus


logger = logging.getLogger(__name__)


class ESPToolAdapter(FlashingServiceInterface, DeviceDiscoveryServiceInterface):
    """Adapter for ESPTool operations on ESP32/ESP8266 devices."""
    
    def __init__(self, baud_rate: int = 921600):
        self.baud_rate = baud_rate
        self.supported_devices = {DeviceType.ESP32, DeviceType.ESP8266}
    
    async def scan_serial_ports(self) -> list[str]:
        """Scan for available serial ports."""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            logger.error(f"Error scanning serial ports: {e}")
            return []
    
    async def scan_network_devices(self) -> list[dict]:
        """Scan for network-connected ESP devices (not implemented)."""
        # ESP devices typically don't support network discovery out of the box
        # This would require custom firmware with mDNS or similar
        return []
    
    async def identify_device_type(self, serial_port: str) -> Optional[DeviceType]:
        """Identify ESP device type from serial port."""
        try:
            device_info = await self._get_chip_info(serial_port)
            chip_type = device_info.get("chip_type", "").lower()
            
            if "esp32" in chip_type:
                return DeviceType.ESP32
            elif "esp8266" in chip_type:
                return DeviceType.ESP8266
            
            return None
        except Exception as e:
            logger.error(f"Error identifying device type on {serial_port}: {e}")
            return None
    
    async def get_device_info(self, serial_port: str) -> dict:
        """Get detailed device information from serial port."""
        return await self._get_chip_info(serial_port)
    
    async def ping_device(self, ip_address: str) -> bool:
        """Ping device at IP address."""
        try:
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1000", ip_address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
    
    async def flash_firmware(
        self,
        device: Device,
        firmware: Firmware,
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ) -> bool:
        """Flash firmware to ESP device."""
        if device.device_type not in self.supported_devices:
            raise ValueError(f"Device type {device.device_type} not supported")
        
        if not device.serial_port:
            raise ValueError("Device serial port not specified")
        
        if not firmware.file_exists():
            raise ValueError("Firmware file does not exist")
        
        try:
            # Notify preparation
            if progress_callback:
                progress_callback(FlashingProgress(
                    status=FlashingStatus.PREPARING,
                    progress_percent=0.0,
                    message="Preparing to flash firmware"
                ))
            
            # Build esptool command
            cmd = self._build_flash_command(device, firmware)
            
            # Execute flashing
            success = await self._execute_esptool_command(
                cmd, progress_callback
            )
            
            if success and progress_callback:
                progress_callback(FlashingProgress(
                    status=FlashingStatus.COMPLETED,
                    progress_percent=100.0,
                    message="Firmware flashed successfully"
                ))
            
            return success
        
        except Exception as e:
            logger.error(f"Error flashing firmware: {e}")
            if progress_callback:
                progress_callback(FlashingProgress(
                    status=FlashingStatus.FAILED,
                    error=str(e)
                ))
            return False
    
    async def erase_device(self, device: Device) -> bool:
        """Erase ESP device flash memory."""
        if device.device_type not in self.supported_devices:
            raise ValueError(f"Device type {device.device_type} not supported")
        
        if not device.serial_port:
            raise ValueError("Device serial port not specified")
        
        try:
            cmd = [
                "--port", device.serial_port,
                "--baud", str(self.baud_rate),
                "erase_flash"
            ]
            
            return await self._execute_esptool_command(cmd)
        
        except Exception as e:
            logger.error(f"Error erasing device: {e}")
            return False
    
    async def verify_firmware(self, device: Device, firmware: Firmware) -> bool:
        """Verify firmware on device (basic implementation)."""
        # ESPTool doesn't have built-in verification beyond write verification
        # This is a placeholder for more advanced verification
        try:
            device_info = await self.read_device_info(device)
            return device_info.get("connected", False)
        except Exception:
            return False
    
    async def read_device_info(self, device: Device) -> dict:
        """Read ESP device information."""
        if not device.serial_port:
            raise ValueError("Device serial port not specified")
        
        return await self._get_chip_info(device.serial_port)
    
    async def check_connection(self, device: Device) -> bool:
        """Check if ESP device is connected and responsive."""
        try:
            info = await self.read_device_info(device)
            return info.get("connected", False)
        except Exception:
            return False
    
    async def reset_device(self, device: Device) -> bool:
        """Reset ESP device."""
        if not device.serial_port:
            raise ValueError("Device serial port not specified")
        
        try:
            # Open serial connection and toggle DTR/RTS for reset
            with serial.Serial(device.serial_port, self.baud_rate, timeout=1) as ser:
                ser.setDTR(False)
                ser.setRTS(True)
                await asyncio.sleep(0.1)
                ser.setDTR(True)
                ser.setRTS(False)
                await asyncio.sleep(0.1)
            
            return True
        except Exception as e:
            logger.error(f"Error resetting device: {e}")
            return False
    
    def _build_flash_command(self, device: Device, firmware: Firmware) -> list[str]:
        """Build esptool flash command."""
        cmd = [
            "--port", device.serial_port,
            "--baud", str(self.baud_rate),
            "write_flash",
            "--flash_mode", "dio",
            "--flash_freq", "40m",
            "--flash_size", "detect",
        ]
        
        # Add flash address (typically 0x0 for ESP devices)
        flash_address = "0x0"
        if device.device_type == DeviceType.ESP8266:
            flash_address = "0x0"
        elif device.device_type == DeviceType.ESP32:
            flash_address = "0x1000"  # ESP32 typically starts at 0x1000
        
        cmd.extend([flash_address, str(firmware.file_path)])
        
        return cmd
    
    async def _execute_esptool_command(
        self,
        cmd: list[str],
        progress_callback: Optional[Callable[[FlashingProgress], None]] = None,
    ) -> bool:
        """Execute esptool command asynchronously."""
        try:
            # Prepare command for subprocess
            full_cmd = ["python", "-m", "esptool"] + cmd
            
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            
            # Monitor output for progress
            if progress_callback:
                await self._monitor_esptool_progress(process, progress_callback)
            
            # Wait for completion
            await process.wait()
            
            return process.returncode == 0
        
        except Exception as e:
            logger.error(f"Error executing esptool command: {e}")
            return False
    
    async def _monitor_esptool_progress(
        self,
        process: asyncio.subprocess.Process,
        progress_callback: Callable[[FlashingProgress], None],
    ) -> None:
        """Monitor esptool output for progress updates."""
        current_status = FlashingStatus.PREPARING
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            line_str = line.decode().strip()
            
            # Parse esptool output for status and progress
            if "Erasing flash" in line_str:
                current_status = FlashingStatus.ERASING
                progress_callback(FlashingProgress(
                    status=current_status,
                    progress_percent=10.0,
                    message="Erasing flash memory"
                ))
            elif "Writing at" in line_str:
                current_status = FlashingStatus.WRITING
                # Try to extract progress percentage
                progress = self._extract_progress_from_line(line_str)
                progress_callback(FlashingProgress(
                    status=current_status,
                    progress_percent=progress,
                    message="Writing firmware"
                ))
            elif "Verifying" in line_str:
                current_status = FlashingStatus.VERIFYING
                progress_callback(FlashingProgress(
                    status=current_status,
                    progress_percent=90.0,
                    message="Verifying firmware"
                ))
    
    def _extract_progress_from_line(self, line: str) -> float:
        """Extract progress percentage from esptool output line."""
        try:
            # Look for percentage in parentheses
            if "(" in line and "%" in line:
                start = line.find("(") + 1
                end = line.find("%")
                if start < end:
                    return float(line[start:end])
        except (ValueError, IndexError):
            pass
        
        return 50.0  # Default progress if can't parse
    
    async def _get_chip_info(self, serial_port: str) -> dict:
        """Get chip information using esptool."""
        try:
            cmd = [
                "--port", serial_port,
                "--baud", str(self.baud_rate),
                "chip_id"
            ]
            
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "esptool", *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                return self._parse_chip_info(output)
            else:
                logger.error(f"ESPTool error: {stderr.decode()}")
                return {"connected": False, "error": stderr.decode()}
        
        except Exception as e:
            logger.error(f"Error getting chip info: {e}")
            return {"connected": False, "error": str(e)}
    
    def _parse_chip_info(self, output: str) -> dict:
        """Parse esptool chip_id output."""
        info = {"connected": True}
        
        lines = output.split("\n")
        for line in lines:
            line = line.strip()
            if "Chip is" in line:
                info["chip_type"] = line.split("Chip is")[1].strip()
            elif "Crystal is" in line:
                info["crystal_freq"] = line.split("Crystal is")[1].strip()
            elif "MAC:" in line:
                info["mac_address"] = line.split("MAC:")[1].strip()
            elif "Flash size:" in line:
                info["flash_size"] = line.split("Flash size:")[1].strip()
        
        return info