#!/usr/bin/env python3
"""Demo del Servicio MQTT AWS IoT Core

Ejemplo de uso del módulo bombercat_mqtt para publicar telemetría y eventos
a AWS IoT Core con reconexión automática.
"""

import asyncio
import json
import logging
import os
import random
import time
from typing import Dict, Any

from modules.bombercat_mqtt import AWSIoTService, MQTTConfig, ConnectionStatus

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MQTTDemo:
    """Demo del servicio MQTT."""
    
    def __init__(self):
        """Inicializa el demo."""
        self.service = None
        self.running = False
        
    def create_service(self) -> AWSIoTService:
        """Crea el servicio MQTT.
        
        Returns:
            Servicio MQTT configurado
        """
        # Opción 1: Desde variables de entorno
        if all(os.getenv(var) for var in [
            'AWS_IOT_ENDPOINT', 'AWS_IOT_CERT_PATH', 
            'AWS_IOT_KEY_PATH', 'AWS_IOT_CA_PATH'
        ]):
            logger.info("Creando servicio desde variables de entorno")
            return AWSIoTService.from_env(device_id="bombercat-demo")
        
        # Opción 2: Configuración manual (para demo)
        logger.info("Creando servicio con configuración de demo")
        config = MQTTConfig(
            endpoint="your-iot-endpoint.iot.region.amazonaws.com",
            cert_path="/path/to/device-cert.pem.crt",
            key_path="/path/to/private.pem.key",
            ca_path="/path/to/AmazonRootCA1.pem",
            device_id="bombercat-demo"
        )
        return AWSIoTService(config)
    
    async def simulate_telemetry(self):
        """Simula datos de telemetría."""
        while self.running:
            try:
                # Generar datos simulados
                telemetry_data = {
                    "temperature": round(random.uniform(20.0, 35.0), 2),
                    "humidity": round(random.uniform(40.0, 80.0), 2),
                    "pressure": round(random.uniform(1000.0, 1020.0), 2),
                    "battery_level": round(random.uniform(0.0, 100.0), 1),
                    "signal_strength": random.randint(-90, -30),
                    "uptime": int(time.time())
                }
                
                # Publicar telemetría
                success = await self.service.publish_telemetry(telemetry_data)
                
                if success:
                    logger.info(f"Telemetría publicada: {telemetry_data}")
                else:
                    logger.warning("Error publicando telemetría")
                
                # Esperar antes de la siguiente publicación
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error en simulación de telemetría: {e}")
                await asyncio.sleep(5)
    
    async def simulate_events(self):
        """Simula eventos del sistema."""
        event_types = [
            ("system_startup", {"version": "1.0.0", "boot_time": time.time()}),
            ("sensor_calibration", {"sensor": "temperature", "status": "completed"}),
            ("maintenance_required", {"component": "battery", "level": "low"}),
            ("data_sync", {"records": random.randint(100, 1000), "status": "success"}),
            ("alert", {"type": "threshold_exceeded", "sensor": "temperature", "value": 40.5})
        ]
        
        while self.running:
            try:
                # Esperar tiempo aleatorio entre eventos
                await asyncio.sleep(random.uniform(30, 120))
                
                # Seleccionar evento aleatorio
                event_type, metadata = random.choice(event_types)
                
                # Publicar evento
                success = await self.service.publish_event(event_type, metadata)
                
                if success:
                    logger.info(f"Evento publicado: {event_type} - {metadata}")
                else:
                    logger.warning(f"Error publicando evento: {event_type}")
                
            except Exception as e:
                logger.error(f"Error en simulación de eventos: {e}")
                await asyncio.sleep(10)
    
    async def monitor_status(self):
        """Monitorea el estado del servicio."""
        while self.running:
            try:
                status = self.service.status()
                
                logger.info(f"Estado del servicio: {status['connection_status']} | "
                           f"Intentos reconexión: {status['reconnect_attempts']} | "
                           f"Última publicación: {status['last_publish_ts']}")
                
                # Mostrar métricas detalladas cada minuto
                if int(time.time()) % 60 == 0:
                    self.show_detailed_status(status)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error monitoreando estado: {e}")
                await asyncio.sleep(10)
    
    def show_detailed_status(self, status: Dict[str, Any]):
        """Muestra estado detallado del servicio.
        
        Args:
            status: Estado del servicio
        """
        logger.info("=== Estado Detallado del Servicio MQTT ===")
        logger.info(f"Cliente ID: {status['client_id']}")
        logger.info(f"Device ID: {status['device_id']}")
        logger.info(f"Endpoint: {status['endpoint']}")
        logger.info(f"Estado: {status['connection_status']}")
        logger.info(f"Conectado: {status['connected']}")
        logger.info(f"Intentos reconexión: {status['reconnect_attempts']}")
        
        if status['last_publish_ts']:
            last_publish = time.time() - status['last_publish_ts']
            logger.info(f"Última publicación: hace {last_publish:.1f}s")
        else:
            logger.info("Última publicación: nunca")
        
        logger.info("============================================")
    
    async def run_demo(self, duration: int = 300):
        """Ejecuta el demo completo.
        
        Args:
            duration: Duración del demo en segundos
        """
        logger.info(f"Iniciando demo MQTT por {duration} segundos...")
        
        try:
            # Crear servicio
            self.service = self.create_service()
            logger.info(f"Servicio creado: {self.service}")
            
            # Iniciar servicio
            logger.info("Iniciando conexión MQTT...")
            connected = await self.service.start()
            
            if not connected:
                logger.error("No se pudo conectar al servicio MQTT")
                return
            
            logger.info("Conexión MQTT establecida exitosamente")
            
            # Publicar evento de inicio
            await self.service.publish_event("demo_started", {
                "duration": duration,
                "timestamp": time.time()
            })
            
            # Iniciar tareas de simulación
            self.running = True
            
            tasks = [
                asyncio.create_task(self.simulate_telemetry()),
                asyncio.create_task(self.simulate_events()),
                asyncio.create_task(self.monitor_status())
            ]
            
            # Ejecutar por el tiempo especificado
            await asyncio.sleep(duration)
            
            # Detener simulación
            self.running = False
            logger.info("Deteniendo simulación...")
            
            # Cancelar tareas
            for task in tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Publicar evento de finalización
            await self.service.publish_event("demo_completed", {
                "duration": duration,
                "timestamp": time.time()
            })
            
            # Detener servicio
            await self.service.stop()
            logger.info("Demo completado exitosamente")
            
        except KeyboardInterrupt:
            logger.info("Demo interrumpido por el usuario")
            self.running = False
            
            if self.service:
                await self.service.stop()
                
        except Exception as e:
            logger.error(f"Error en demo: {e}")
            self.running = False
            
            if self.service:
                await self.service.stop()


async def main():
    """Función principal del demo."""
    print("🚀 Demo del Servicio MQTT AWS IoT Core")
    print("======================================")
    print()
    print("Este demo simula un dispositivo IoT que publica:")
    print("• Telemetría cada 10 segundos (temperatura, humedad, etc.)")
    print("• Eventos aleatorios del sistema")
    print("• Monitoreo del estado de conexión")
    print()
    print("Configuración requerida:")
    print("• Variables de entorno AWS_IOT_* o configuración manual")
    print("• Certificados y claves de AWS IoT Core")
    print()
    
    # Verificar configuración
    env_vars = ['AWS_IOT_ENDPOINT', 'AWS_IOT_CERT_PATH', 'AWS_IOT_KEY_PATH', 'AWS_IOT_CA_PATH']
    missing_vars = [var for var in env_vars if not os.getenv(var)]
    
    if missing_vars:
        print("⚠️  Variables de entorno faltantes:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("💡 Para configurar AWS IoT Core, consulta: docs/mqtt_setup.md")
        print()
        print("🔧 Ejecutando demo con configuración simulada...")
    else:
        print("✅ Configuración de AWS IoT detectada")
    
    print()
    
    # Ejecutar demo
    demo = MQTTDemo()
    await demo.run_demo(duration=120)  # 2 minutos de demo


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo interrumpido. ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error ejecutando demo: {e}")