# MeshAdv Mini

The MeshAdv Mini is a Raspberry Pi hat designed to be used with the Linux-native version of Meshtastic known as meshtasticd. The board includes a +22dbm LoRa module, an onboard GPS module, Real Time Clock, Temperature Sensor, and breakout for I2C bus including two Qwiic connectors. 
This makes for a good "base station" or "Router" node that can be mounted high on a pole and powered over POE (using separate POE adapter or Hat). No more need to retrieve the node everytime you want to update firmware, it can all be done remotely. It also makes it easy and reliable to connect to MQTT.



Some PCB's may be available here: https://frequencylabs.etsy.com 

![](https://github.com/chrismyers2000/MeshAdv-Mini/blob/8c91e4e708419ff6cd2cfe6af8cbe80a86944f7a/Photos/3D_PCB%20MeshAdv%20Mini%20side.png)

# Info

|Pin# |GPIO|Pin Name   |Description            |   |   |Pin# |GPIO|Pin Name   |Description                      |
|-----|----|-----------|-----------------------|---|---|-----|----|-----------|---------------------------------|
|1    |    |3.3V       |                       |   |   |2    |    |5V         |                                 |
|3    |2   |SDA        |(I2C)                  |   |   |4    |    |5V         |                                 |
|5    |3   |SCL        |(I2C)                  |   |   |6    |    |GND        |                                 |
|7    |4   |GPSEN      |(GPS) GPS Enable       |   |   |8    |14  |UART TX    |(GPS)RX                          |
|9    |    |GND        |                       |   |   |10   |15  |UART RX    |(GPS)TX                          |
|11   |17  |PPS        |(GPS)                  |   |   |12   |18  |FANPWM     |Fan Speed PWM                    |
|13   |27  |Unused     |                       |   |   |14   |    |GND        |                                 |
|15   |22  |Unused     |                       |   |   |16   |23  |Unused     |                                 |
|17   |    |3.3V       |                       |   |   |18   |24  |RST        |(LoRa)                           |
|19   |10  |MOSI       |(LoRa)                 |   |   |20   |    |GND        |                                 |
|21   |9   |MISO       |(LoRa)                 |   |   |22   |25  |Unused     |                                 |
|23   |11  |CLK        |(LoRa)                 |   |   |24   |8   |CS1        |Chip Select 1 (Default)          |
|25   |    |GND        |                       |   |   |26   |7   |CS2        |Chip Select 2 (For second Radio) |
|27   |0   |Unused     |                       |   |   |28   |1   |Unused     |                                 |
|29   |5   |Unused     |                       |   |   |30   |    |GND        |                                 |
|31   |6   |Unused     |                       |   |   |32   |12  |RXEN       |(LoRa) Recieve Enable            |
|33   |13  |TXEN       |(LoRa) Transmit Enable |   |   |34   |    |GND        |                                 |
|35   |19  |Unused     |                       |   |   |36   |16  |IRQ        |(LoRa)                           |
|37   |26  |Unused     |                       |   |   |38   |20  |BUSY       |(LoRa)                           |
|39   |    |GND        |                       |   |   |40   |21  |Unused     |                                 |

== NOTICE!! always have an antenna connected to the Hat when powered on, failure to do so can damage the E22 module. ==



# Compatibility

| Raspberry Pi Model      | Working? |
|-------------------------|----------|
| Raspberry Pi 1 Model A  | No       |
| Raspberry Pi 1 Model A+ | No       |
| Raspberry Pi 1 Model B  | No       |
| Raspberry Pi 1 Model B+ | No       |
| Raspberry Pi 2 Model B  | ???      |
| Raspberry Pi 3 Model B  | ???      |
| Raspberry Pi 3 Model B+ | Yes      |
| Raspberry Pi 3 Model A+ | Yes      |
| Raspberry Pi 4 Model B  | Yes      |
| Raspberry Pi 400        | Yes      |
| Raspberry Pi 5          | Yes      |
| Raspberry Pi 500        | Yes      |
| Raspberry Pi Zero       | Yes      |
| Raspberry Pi Zero W     | Yes      |
| Raspberry Pi Zero 2 W   | Yes      |
| Raspberry Pi Pico       | Never    |
| Raspberry Pi Pico W     | Never    |





# Installing Meshtasticd

~~Watch this video first: [How to install Meshtastic on Raspberry Pi](https://www.youtube.com/watch?v=vLGoEPNT0Mk)~~ This video covers the old method, still a good video but out of date.


Official installation instructions: [https://meshtastic.org/docs/hardware/devices/linux-native-hardware/]



# Configuration

Click here for the new configuration method: [https://meshtastic.org/docs/hardware/devices/linux-native-hardware/#configuration]

The old method is below and still works if you prefer it


In /etc/meshtasticd/config.yaml, add or uncomment the following lines as needed.
```yaml
Lora:
  Module: sx1262  # Ebyte E22-900M22S choose only one module at a time
# Module: sx1268  # Ebyte E22 400M22S
# JP1 will allow you to use 2 radios. CS1 is default, cut the jumper and solder the other pads for CS2. (This feature is experimental)
  CS: 8  #  CS1 (Default)
# CS: 7  #  CS2 
  IRQ: 16
  Busy: 20
  Reset: 24
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
  RootPath: /usr/share/meshtasticd/web # Root Dir of WebServer

General:
  MaxNodes: 200
```

