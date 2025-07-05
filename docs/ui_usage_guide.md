# 🎯 Guía de Uso - BomberCat Integrator UI

## 📋 Descripción General

La interfaz de usuario del BomberCat Integrator es una aplicación Flet que proporciona una experiencia visual completa para gestionar dispositivos ESP32, flashear firmware, configurar dispositivos y monitorear el sistema en tiempo real.

## 🚀 Acceso a la Aplicación

### URLs de Acceso
- **Interfaz Web:** http://localhost:8550
- **API Backend:** http://localhost:8000
- **Documentación API:** http://localhost:8000/docs

### Inicio de la Aplicación
```bash
# Desde el directorio raíz del proyecto
python3 ui/main.py
```

## 🏠 Pantalla Principal (Dashboard)

### Panel de Estado del Sistema
- **Estado de Servicios:** Muestra el estado de todos los servicios (Flash, Config, Relay, MQTT)
- **Conexiones WebSocket:** Número de clientes conectados
- **Métricas en Tiempo Real:** CPU, memoria, latencia
- **Estado MQTT:** Conexión y estadísticas de mensajes

### Indicadores Visuales
- 🟢 **Verde:** Servicio funcionando correctamente
- 🟡 **Amarillo:** Servicio con advertencias
- 🔴 **Rojo:** Servicio con errores o desconectado
- ⚪ **Gris:** Servicio no disponible

## 🔧 Sección de Flasheo

### Detección Automática de Dispositivos
1. **Conecta tu ESP32** al puerto USB
2. La aplicación **detecta automáticamente** el dispositivo
3. Se muestra información del chip:
   - Tipo de chip (ESP32, ESP32-S2, ESP32-C3, etc.)
   - Puerto serie detectado
   - Estado de conexión

### Proceso de Flasheo
1. **Seleccionar Firmware:**
   - Usa el botón "Seleccionar Firmware"
   - Navega y selecciona el archivo `.bin`
   - Se valida automáticamente el archivo

2. **Configurar Parámetros:**
   - **Puerto:** Se autodetecta, pero puedes cambiarlo manualmente
   - **Velocidad:** 115200, 460800, 921600 bps (recomendado: 460800)
   - **Dirección Flash:** 0x0000 (por defecto)

3. **Iniciar Flasheo:**
   - Presiona "Iniciar Flash"
   - **Barra de progreso** muestra el avance en tiempo real
   - **Log de actividad** muestra detalles del proceso
   - **Tiempo estimado** y velocidad de transferencia

### Estados del Flasheo
- **🔍 Detectando:** Buscando dispositivos
- **⚡ Preparando:** Configurando parámetros
- **📤 Flasheando:** Transfiriendo firmware
- **✅ Completado:** Flash exitoso
- **❌ Error:** Problema durante el proceso

## ⚙️ Configuración de Dispositivos

### Configuración WiFi
1. **SSID:** Nombre de la red WiFi
2. **Contraseña:** Clave de la red
3. **Modo:** Cliente, AP, o Dual
4. **Canal:** Canal WiFi (1-13)

### Configuración MQTT
1. **Broker:** Dirección del servidor MQTT
2. **Puerto:** Puerto de conexión (1883, 8883)
3. **Usuario/Contraseña:** Credenciales de autenticación
4. **Tópicos:** Configuración de tópicos de publicación/suscripción

### Configuración de Hardware
1. **Pines GPIO:** Asignación de pines para sensores/actuadores
2. **Protocolos:** I2C, SPI, UART
3. **Frecuencias:** Configuración de relojes

### Aplicar Configuración
1. **Edita los valores** en los campos correspondientes
2. **Valida la configuración** (se hace automáticamente)
3. **Presiona "Aplicar Configuración"**
4. **Confirma los cambios** en el diálogo
5. **Monitorea el resultado** en el log de actividad

## 🔄 Relay TCP

### Configuración del Relay
1. **Puerto Origen:** Puerto local donde escucha el relay
2. **Host Destino:** Dirección IP del dispositivo objetivo
3. **Puerto Destino:** Puerto del dispositivo objetivo
4. **Protocolo:** TCP/UDP

### Control del Relay
- **▶️ Iniciar Relay:** Comienza el servicio de relay
- **⏹️ Detener Relay:** Detiene el servicio
- **📊 Métricas:** Latencia, throughput, conexiones activas
- **📈 Gráficos:** Visualización en tiempo real del tráfico

### Monitoreo en Tiempo Real
- **Conexiones Activas:** Número de clientes conectados
- **Bytes Transferidos:** Entrada y salida
- **Latencia Promedio:** Tiempo de respuesta
- **Errores:** Conexiones fallidas o timeouts

## 📊 Monitoreo y Logs

### Panel de Logs
- **Filtros por Nivel:** DEBUG, INFO, WARNING, ERROR
- **Filtros por Servicio:** Flash, Config, Relay, MQTT
- **Búsqueda:** Buscar texto específico en logs
- **Exportar:** Guardar logs en archivo

### Métricas del Sistema
- **CPU:** Uso del procesador
- **Memoria:** RAM utilizada
- **Red:** Tráfico de entrada/salida
- **Disco:** Espacio disponible

### Alertas y Notificaciones
- **🔔 Notificaciones Push:** Para eventos importantes
- **📧 Email:** Alertas críticas (si está configurado)
- **📱 Toast:** Mensajes emergentes en la UI

## 🛠️ Herramientas Avanzadas

### Terminal Integrado
- **Comandos esptool:** Acceso directo a herramientas de flash
- **Comandos sistema:** Diagnósticos del sistema
- **Scripts personalizados:** Automatización de tareas

### Backup y Restauración
- **Backup Configuración:** Guardar configuraciones actuales
- **Restaurar:** Cargar configuraciones previas
- **Exportar/Importar:** Compartir configuraciones

### Diagnósticos
- **Test de Conectividad:** Verificar conexiones
- **Test de Hardware:** Validar funcionamiento de componentes
- **Benchmark:** Pruebas de rendimiento

## 🔧 Configuración de la UI

### Preferencias de Usuario
1. **Tema:** Claro, Oscuro, Automático
2. **Idioma:** Español, Inglés
3. **Actualizaciones:** Frecuencia de refresh
4. **Notificaciones:** Configurar alertas

### Personalización
- **Layout:** Organizar paneles según preferencias
- **Widgets:** Mostrar/ocultar componentes
- **Colores:** Personalizar esquema de colores

## 🚨 Solución de Problemas

### Problemas Comunes

#### Dispositivo No Detectado
1. **Verificar conexión USB**
2. **Instalar drivers** del chip USB-Serial
3. **Revisar permisos** de puerto serie
4. **Probar otro cable USB**

#### Error de Flash
1. **Verificar archivo firmware** (formato .bin)
2. **Comprobar velocidad** de conexión
3. **Resetear dispositivo** antes del flash
4. **Revisar logs** para detalles del error

#### Problemas de Conectividad
1. **Verificar red WiFi**
2. **Comprobar credenciales**
3. **Revisar firewall**
4. **Validar configuración MQTT**

### Logs de Diagnóstico
- **Nivel DEBUG:** Para desarrollo y diagnóstico detallado
- **Exportar logs:** Para soporte técnico
- **Limpiar logs:** Para liberar espacio

## 📱 Atajos de Teclado

- **Ctrl+R:** Actualizar datos
- **Ctrl+L:** Limpiar logs
- **Ctrl+S:** Guardar configuración
- **Ctrl+O:** Abrir archivo firmware
- **F5:** Detectar dispositivos
- **F11:** Pantalla completa
- **Esc:** Cancelar operación actual

## 🔄 Actualizaciones en Tiempo Real

La interfaz se actualiza automáticamente mediante WebSocket:
- **Estado de dispositivos:** Cada 1 segundo
- **Métricas del sistema:** Cada 100ms
- **Progreso de flash:** En tiempo real
- **Logs:** Instantáneo

## 💡 Consejos de Uso

1. **Mantén la aplicación abierta** para recibir actualizaciones en tiempo real
2. **Usa la detección automática** antes de flashear manualmente
3. **Revisa los logs** si algo no funciona como esperado
4. **Haz backup** de configuraciones importantes
5. **Actualiza regularmente** el firmware de tus dispositivos
6. **Monitorea las métricas** para optimizar el rendimiento

## 🆘 Soporte

Si encuentras problemas:
1. **Revisa esta guía** para soluciones comunes
2. **Consulta los logs** para detalles del error
3. **Exporta logs** para análisis técnico
4. **Documenta los pasos** para reproducir el problema

---

**¡Disfruta usando BomberCat Integrator! 🚀**
