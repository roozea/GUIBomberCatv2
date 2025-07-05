# Permisos USB para Dispositivos BomberCat (ESP32-S2)

Esta guía explica cómo configurar los permisos necesarios para acceder a dispositivos ESP32-S2 en diferentes sistemas operativos.

## Linux

### Configuración de Reglas udev

Para acceder a dispositivos ESP32-S2 sin permisos de administrador, necesitas configurar reglas udev:

1. **Crear archivo de reglas udev:**
   ```bash
   sudo nano /etc/udev/rules.d/99-bombercat.rules
   ```

2. **Añadir las siguientes reglas:**
   ```bash
   # Espressif ESP32-S2
   SUBSYSTEM=="usb", ATTR{idVendor}=="303a", ATTR{idProduct}=="0002", MODE="0666", GROUP="dialout"
   
   # Silicon Labs CP210x (común en dev boards ESP32)
   SUBSYSTEM=="usb", ATTR{idVendor}=="10c4", ATTR{idProduct}=="ea60", MODE="0666", GROUP="dialout"
   
   # QinHeng Electronics CH340
   SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="7523", MODE="0666", GROUP="dialout"
   
   # FTDI FT232R
   SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6001", MODE="0666", GROUP="dialout"
   
   # Reglas para puertos serie
   KERNEL=="ttyUSB*", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="0002", MODE="0666", GROUP="dialout"
   KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="dialout"
   KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="dialout"
   KERNEL=="ttyUSB*", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0666", GROUP="dialout"
   
   # Para dispositivos ACM (algunos ESP32 aparecen como ttyACM)
   KERNEL=="ttyACM*", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="0002", MODE="0666", GROUP="dialout"
   ```

3. **Recargar reglas udev:**
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

### Añadir Usuario al Grupo dialout

```bash
sudo usermod -a -G dialout $USER
```

**Importante:** Después de ejecutar este comando, debes cerrar sesión y volver a iniciarla para que los cambios surtan efecto.

### Verificar Configuración

1. **Verificar pertenencia al grupo:**
   ```bash
   groups $USER
   ```
   Deberías ver `dialout` en la lista.

2. **Verificar permisos del dispositivo:**
   ```bash
   ls -l /dev/ttyUSB*
   ls -l /dev/ttyACM*
   ```
   Los dispositivos deberían mostrar permisos `crw-rw-rw-` o similar.

### Solución de Problemas en Linux

- **Error "Permission denied":** Verifica que el usuario esté en el grupo `dialout` y que las reglas udev estén aplicadas.
- **Dispositivo no detectado:** Usa `lsusb` para verificar que el dispositivo esté conectado y reconocido.
- **Puerto ocupado:** Asegúrate de que no haya otros programas (como Arduino IDE o monitor serie) usando el puerto.

## macOS

### Configuración General

En macOS, generalmente no se requieren permisos especiales para acceder a dispositivos USB serie. Sin embargo, pueden ser necesarios drivers específicos.

### Instalación de Drivers

1. **Driver Silicon Labs CP210x (recomendado):**
   ```bash
   brew install --cask silicon-labs-vcp-driver
   ```
   
   O descarga manualmente desde: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers

2. **Driver CH340 (si es necesario):**
   Descarga desde: https://github.com/adrianmihalko/ch340g-ch34g-ch34x-mac-os-x-driver

### Verificar Dispositivos en macOS

```bash
# Listar dispositivos USB
system_profiler SPUSBDataType | grep -A 10 -B 10 "ESP32\|CP210\|CH340"

# Listar puertos serie
ls /dev/cu.*
ls /dev/tty.*
```

### Solución de Problemas en macOS

- **Dispositivo no aparece:** Instala el driver apropiado (CP210x es el más común).
- **Permisos denegados:** Verifica en "Preferencias del Sistema > Seguridad y Privacidad" si hay algún software bloqueado.
- **Puerto no disponible:** Usa `/dev/cu.*` en lugar de `/dev/tty.*` para evitar problemas de bloqueo.

## Windows

### Instalación de Drivers

1. **Driver Silicon Labs CP210x:**
   - Descarga desde: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
   - Ejecuta el instalador como administrador
   - Reinicia el sistema si es necesario

2. **Driver CH340:**
   - Descarga desde: http://www.wch.cn/downloads/CH341SER_EXE.html
   - Ejecuta como administrador

3. **Driver FTDI (si es necesario):**
   - Descarga desde: https://ftdichip.com/drivers/vcp-drivers/

### Verificar Instalación en Windows

1. **Administrador de Dispositivos:**
   - Abre "Administrador de dispositivos"
   - Busca en "Puertos (COM y LPT)"
   - Deberías ver algo como "Silicon Labs CP210x USB to UART Bridge (COM3)"

2. **Línea de comandos:**
   ```cmd
   # PowerShell
   Get-WmiObject -Class Win32_SerialPort | Select-Object Name, DeviceID, Description
   
   # CMD
   wmic path win32_serialport get deviceid,name,description
   ```

### Solución de Problemas en Windows

- **Dispositivo no reconocido:** Instala el driver apropiado y reinicia.
- **Puerto COM no aparece:** Verifica en el Administrador de Dispositivos si hay dispositivos con errores.
- **Error de acceso:** Asegúrate de que no haya otros programas usando el puerto.
- **Driver no firmado:** En Windows 10/11, puede ser necesario deshabilitar temporalmente la verificación de firma de drivers.

## Verificación Multiplataforma

### Usando Python

```python
import serial.tools.list_ports

# Listar todos los puertos
ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"Puerto: {port.device}")
    print(f"Descripción: {port.description}")
    print(f"HWID: {port.hwid}")
    print(f"VID:PID: {port.vid:04X}:{port.pid:04X}" if port.vid and port.pid else "VID:PID: N/A")
    print("-" * 40)
```

### Usando esptool

```bash
# Detectar chip en puerto específico
esptool.py --port /dev/ttyUSB0 chip_id  # Linux/macOS
esptool.py --port COM3 chip_id          # Windows

# Escanear puertos automáticamente
python -m esptool chip_id
```

## Notas Importantes

1. **Desconectar otros programas:** Antes de usar el detector, asegúrate de cerrar cualquier monitor serie, Arduino IDE, o software similar que pueda estar usando los puertos.

2. **Reiniciar después de cambios:** En Linux y Windows, puede ser necesario reiniciar después de instalar drivers o cambiar permisos.

3. **Múltiples dispositivos:** Si tienes múltiples dispositivos ESP32-S2 conectados, cada uno aparecerá en un puerto diferente.

4. **Cables USB:** Asegúrate de usar un cable USB de datos (no solo de carga). Algunos cables micro-USB solo transfieren energía.

5. **Modo de descarga:** Algunos dispositivos ESP32-S2 requieren entrar en modo de descarga manualmente (presionar botón BOOT mientras se conecta).

## Contacto y Soporte

Si encuentras problemas no cubiertos en esta guía:

1. Verifica que el dispositivo funcione con otras herramientas (Arduino IDE, esptool directo)
2. Revisa los logs del sistema para errores relacionados con USB
3. Consulta la documentación específica de tu placa de desarrollo ESP32-S2