"""Interfaces package for adapters.

Define interfaces para repositorios y servicios."""

from .base_service import (
    BaseService,
    ServiceStatus,
    WebSocketManagerInterface,
    FlashServiceInterface,
    ConfigServiceInterface,
    RelayServiceInterface,
    MQTTServiceInterface
)

# Aliases para compatibilidad
BaseFlashServiceInterface = FlashServiceInterface
BaseConfigServiceInterface = ConfigServiceInterface
BaseRelayServiceInterface = RelayServiceInterface
BaseMQTTServiceInterface = MQTTServiceInterface