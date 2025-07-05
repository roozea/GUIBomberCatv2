"""Firmware domain entity."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import UUID, uuid4


class FirmwareType(Enum):
    """Types of firmware files."""
    BINARY = "binary"
    HEX = "hex"
    ELF = "elf"


@dataclass
class FirmwareVersion:
    """Firmware version information."""
    major: int
    minor: int
    patch: int
    build: Optional[str] = None
    
    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.build:
            version += f"-{self.build}"
        return version
    
    @classmethod
    def from_string(cls, version_str: str) -> "FirmwareVersion":
        """Parse version string into FirmwareVersion."""
        parts = version_str.split("-")
        version_parts = parts[0].split(".")
        
        if len(version_parts) != 3:
            raise ValueError(f"Invalid version format: {version_str}")
        
        major, minor, patch = map(int, version_parts)
        build = parts[1] if len(parts) > 1 else None
        
        return cls(major=major, minor=minor, patch=patch, build=build)
    
    def __lt__(self, other: "FirmwareVersion") -> bool:
        """Compare firmware versions."""
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __eq__(self, other: object) -> bool:
        """Check firmware version equality."""
        if not isinstance(other, FirmwareVersion):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.build == other.build
        )


@dataclass
class Firmware:
    """Firmware entity representing a firmware file and its metadata."""
    
    id: UUID
    name: str
    version: FirmwareVersion
    file_path: Path
    file_size: int
    checksum: str
    firmware_type: FirmwareType
    target_devices: list[str]  # Device types this firmware supports
    description: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def create(
        cls,
        name: str,
        version: FirmwareVersion,
        file_path: Path,
        file_size: int,
        checksum: str,
        firmware_type: FirmwareType,
        target_devices: list[str],
        description: Optional[str] = None,
    ) -> "Firmware":
        """Create a new firmware instance."""
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            name=name,
            version=version,
            file_path=file_path,
            file_size=file_size,
            checksum=checksum,
            firmware_type=firmware_type,
            target_devices=target_devices,
            description=description,
            metadata={},
            created_at=now,
            updated_at=now,
        )
    
    def is_compatible_with(self, device_type: str) -> bool:
        """Check if firmware is compatible with device type."""
        return device_type.lower() in [dt.lower() for dt in self.target_devices]
    
    def file_exists(self) -> bool:
        """Check if firmware file exists on disk."""
        return self.file_path.exists() and self.file_path.is_file()
    
    def get_file_extension(self) -> str:
        """Get firmware file extension."""
        return self.file_path.suffix.lower()