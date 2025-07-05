"""BomberCat MQTT Service

Módulo para publicar telemetría y eventos a AWS IoT Core sobre MQTT + TLS,
con reconexión automática y métricas de estado.
"""

from modules.bombercat_mqtt.aws_iot_service import AWSIoTService, ConnectionStatus, MQTTConfig
from modules.bombercat_mqtt.backoff import ExponentialBackoff, ConnectionRetryManager

__version__ = "1.0.0"
__all__ = [
    "AWSIoTService",
    "ConnectionStatus",
    "MQTTConfig",
    "ExponentialBackoff",
    "ConnectionRetryManager"
]