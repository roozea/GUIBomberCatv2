"""BomberCat NFC Relay Core

Módulo para relay NFC bidireccional de alta velocidad con latencia < 5ms.
Soporta buffers zero-copy, validación APDU y monitoreo en tiempo real.
"""

from modules.bombercat_relay.ring_buffer import RingBuffer
from modules.bombercat_relay.apdu import APDU, is_complete, parse_apdu
from modules.bombercat_relay.serial_pipeline import SerialPipeline
from modules.bombercat_relay.metrics import LatencyMeter
from modules.bombercat_relay.relay_core import NFCRelayService, RelayError

__version__ = "1.0.0"
__all__ = [
    "RingBuffer",
    "APDU",
    "is_complete",
    "parse_apdu",
    "SerialPipeline",
    "LatencyMeter",
    "NFCRelayService",
    "RelayError",
]