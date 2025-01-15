# MeshAdv Mini

The MeshAdv Mini is a Raspberry Pi hat designed to be used with the Linux-native version of Meshtastic known as meshtasticd. The board includes an onboard GPS module and breakout for I2C bus including two Qwiic connectors. 
This makes for a good "base station" or "Router" node that can be mounted high on a pole and powered over POE (using separate POE adapter or Hat). No more need to retrieve the node everytime you want to update firmware, it can all be done remotely. It also makes it easy and reliable to connect to MQTT.



Some PCB's may be available here: https://frequencylabs.etsy.com New batch has arrived!

![](https://github.com/chrismyers2000/MeshAdv-Pi-Hat/blob/2fb02e426bd7faad89f40714b303855255108235/V1.1/SMA/Photos/3D_PCB%20V1.1_SMA_Top.png)

# Info

== NOTICE!! always have an antenna connected to the Hat when powered on, failure to do so can damage the E22 module. ==


# Installing Meshtasticd

Watch this video first: [How to install Meshtastic on Raspberry Pi](https://www.youtube.com/watch?v=vLGoEPNT0Mk)

I followed the video exactly and had no problems. I was using a Raspberry Pi Zero 2 W running 64bit Raspberry Pi OS Debian Bookworm. Using the official "Raspberry Pi Imager" makes this very easy.

https://meshtastic.org/docs/hardware/devices/linux-native-hardware/

https://meshtastic.org/docs/software/linux-native/


# Configuration


In /etc/meshtasticd/config.yaml, add or uncomment the following lines as needed.
```yaml
Lora:
  Module: sx1262  # Ebyte E22-900M30S and E22-900M33S choose only one module at a time
# Module: sx1268  # Ebyte E22 400M30S and E22-400M33S
  CS: 21
  IRQ: 16
  Busy: 20
  Reset: 18
  TXen: 13
  RXen: 12
  DIO3_TCXO_VOLTAGE: true

GPS:
  SerialPath: /dev/ttyS0

I2C:
  I2CDevice: /dev/i2c-1

Logging:
  LogLevel: info # debug, info, warn, error

Webserver:
  Port: 443 # Port for Webserver & Webservices
  RootPath: /usr/share/doc/meshtasticd/web # Root Dir of WebServer

General:
  MaxNodes: 200
```

